# Copyright 2018 Datawire. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License

import sys

import json
import logging
import os
# import time
import traceback
# import uuid
import yaml

import clize
from clize import Parameter

from .config import Config, ACResource
from .ir import IR
from .envoy import V1Config

from .utils import RichStatus

from .VERSION import Version

__version__ = Version

logging.basicConfig(
    level=logging.INFO, # if appDebug else logging.INFO,
    format="%%(asctime)s ambassador %s %%(levelname)s: %%(message)s" % __version__,
    datefmt="%Y-%m-%d %H:%M:%S"
)

# logging.getLogger("datawire.scout").setLevel(logging.DEBUG)
logger = logging.getLogger("ambassador")
logger.setLevel(logging.DEBUG)

def handle_exception(what, e, **kwargs):
    tb = "\n".join(traceback.format_exception(*sys.exc_info()))

    # if Config.scout:
    #     result = Config.scout_report(action=what, mode="cli", exception=str(e), traceback=tb,
    #                                  runtime=Config.runtime, **kwargs)
    #
    #     logger.debug("Scout %s, result: %s" %
    #                  ("disabled" if Config.scout.disabled else "enabled", result))

    logger.error("%s: %s\n%s" % (what, e, tb))

    show_notices()

def show_notices(printer=logger.log):
    # if Config.scout_notices:
    #     for notice in Config.scout_notices:
    #         try:
    #             if isinstance(notice, str):
    #                 printer(logging.WARNING, notice)
    #             else:
    #                 lvl = notice['level'].upper()
    #                 msg = notice['message']
    #
    #                 if isinstance(lvl, str):
    #                     lvl = getattr(logging, lvl, logging.INFO)
    #
    #                 printer(lvl, msg)
    #         except KeyError:
    #             printer(logging.WARNING, json.dumps(notice))
    print("CANNOT SHOW NOTICES RIGHT NOW")

def stdout_printer(lvl, msg):
    print("%s: %s" % (logging.getLevelName(lvl), msg))

def version():
    """
    Show Ambassador's version
    """

    print("Ambassador %s" % __version__)

    # if Config.scout:
    #     Config.scout_report(action="version", mode="cli")
    #     show_notices(printer=stdout_printer)

def showid():
    """
    Show Ambassador's installation ID
    """

    # if Config.scout:
    #     print("%s" % Config.scout.install_id)
    #
    #     Config.scout_report(action="showid", mode="cli")
    #
    #     show_notices(printer=stdout_printer)
    # else:
    #     print("unknown")
    print("CANNOT SHOW ID RIGHT NOW")

def fetch_resources(config_dir_path):
    all_resources = []

    for filename in os.listdir(config_dir_path):
        filepath = os.path.join(config_dir_path, filename)

        if not os.path.isfile(filepath):
            continue

        serialization = open(filepath, "r").read()

        objects = list(yaml.safe_load_all(serialization))

        ocount = 0

        for obj in objects:
            ocount += 1
            rkey = "%s.%d" % (os.path.basename(filepath), ocount)

            r = ACResource.from_dict(rkey, rkey, serialization, obj)

            all_resources.append(r)

    return all_resources

def parse_config(config_dir_path, schema_dir_path=None):
    try:
        resources = fetch_resources(config_dir_path)
        aconf = Config(schema_dir_path=schema_dir_path)
        aconf.load_all(resources)
    except Exception as e:
        handle_exception("EXCEPTION from parse_config", e,
                         config_dir_path=config_dir_path, template_dir_path=template_dir_path,
                         schema_dir_path=schema_dir_path)

        # This is fatal.
        sys.exit(1)

def dump(config_dir_path:Parameter.REQUIRED):
    """
    Dump the intermediate form of an Ambassador configuration for debugging

    :param config_dir_path: Configuration directory to scan for Ambassador YAML files
    """

    try:
        resources = fetch_resources(config_dir_path)
        aconf = Config()
        aconf.load_all(resources)

        # diag_object = {
        #     'envoy_config': aconf.envoy_config,
        #     '_errors': aconf.errors,
        #     'sources': aconf.sources,
        #     'source_map': aconf.source_map
        # }
        #
        # json.dump(diag_object, sys.stdout, indent=4, sort_keys=True)
        aconf.dump()
    except Exception as e:
        handle_exception("EXCEPTION from dump", e,
                         config_dir_path=config_dir_path)

        # This is fatal.
        sys.exit(1)

def validate(config_dir_path:Parameter.REQUIRED, *, k8s=False):
    """
    Validate an Ambassador configuration

    :param config_dir_path: Configuration directory to scan for Ambassador YAML files
    :param k8s: If set, assume configuration files are annotated K8s manifests
    """
    config(config_dir_path, os.devnull, exit_on_error=True)

def config(config_dir_path:Parameter.REQUIRED, output_json_path:Parameter.REQUIRED, *,
           check=False, exit_on_error=False):
    """
    Generate an Envoy configuration

    :param config_dir_path: Configuration directory to scan for Ambassador YAML files
    :param output_json_path: Path to output envoy.json
    :param check: If set, generate configuration only if it doesn't already exist
    :param k8s: If set, assume configuration files are annotated K8s manifests
    :param exit_on_error: If set, will exit with status 1 on any configuration error
    """

    try:
        logger.debug("CHECK MODE  %s" % check)
        logger.debug("CONFIG DIR  %s" % config_dir_path)
        logger.debug("OUTPUT PATH %s" % output_json_path)

        # Bypass the existence check...
        output_exists = False

        if check:
            # ...oh no wait, they explicitly asked for the existence check!
            # Assume that the file exists (ie, we'll do nothing) unless we
            # determine otherwise.
            output_exists = True

            try:
                x = json.loads(open(output_json_path, "r").read())
            except FileNotFoundError:
                logger.debug("output file does not exist")
                output_exists = False
            except OSError:
                logger.warning("output file is not sane?")
                output_exists = False
            except json.decoder.JSONDecodeError:
                logger.warning("output file is not valid JSON")
                output_exists = False

            logger.info("Output file %s" % ("exists" if output_exists else "does not exist"))

        rc = RichStatus.fromError("impossible error")

        if not output_exists:
            # Either we didn't need to check, or the check didn't turn up
            # a valid config. Regenerate.
            logger.info("Generating new Envoy configuration...")

            resources = fetch_resources(config_dir_path)
            aconf = Config()
            aconf.load_all(resources)

            # If exit_on_error is set, log _errors and exit with status 1
            if exit_on_error and aconf.errors:
                raise Exception("_errors in: {0}".format(', '.join(aconf.errors.keys())))

            ir = IR(aconf)
            v1config = V1Config(ir)
            rc = RichStatus.OK(msg="huh")

            if rc:
                with open(output_json_path, "w") as output:
                    output.write(v1config.as_json())
                    output.write("\n")
            else:
                logger.error("Could not generate new Envoy configuration: %s" % rc.error)


        show_notices()
    except Exception as e:
        handle_exception("EXCEPTION from config", e,
                         config_dir_path=config_dir_path, output_json_path=output_json_path)

        # This is fatal.
        sys.exit(1)

def main():
    clize.run([config, dump, validate], alt=[version, showid],
              description="""
              Generate an Envoy config, or manage an Ambassador deployment. Use

              ambassador.py command --help

              for more help, or

              ambassador.py --version

              to see Ambassador's version.
              """)

if __name__ == "__main__":
    main()