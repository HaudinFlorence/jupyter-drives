"""
Module with all of the individual handlers, which will return the results to the frontend.
"""
import json
import os
import functools
import logging 
import traceback
from typing import Optional, Tuple, Union

from jupyter_server.base.handlers import APIHandler
from jupyter_server.services.contents.manager import ContentsManager
from jupyter_server.utils import url2path, url_path_join
import tornado
import traitlets

from .base import MANAGERS, DrivesConfig
from .managers.manager import JupyterDrivesManager

NAMESPACE = "jupyter-drives"

class JupyterDrivesAPIHandler(APIHandler):
    """
    Base handler for jupyter-drives specific API handlers
    """
    def initialize(self, logger: logging.Logger, manager: JupyterDrivesManager):
        self._jp_log = logger
        self._manager = manager

    def write_error(self, status_code, **kwargs):
        """
        Override Tornado's RequestHandler.write_error for customized error handlings
        This method will be called when an exception is raised from a handler
        """
        self.set_header("Content-Type", "application/json")
        reply = {"error": "Unhandled error"}
        exc_info = kwargs.get("exc_info")
        if exc_info:
            e = exc_info[1]
            if isinstance(e, tornado.web.HTTPError):
                reply["error"] = e.reason
                if hasattr(e, "error_code"):
                    reply["error_code"] = e.error_code
            else:
                reply["error"] = "".join(traceback.format_exception(*exc_info))
        self.finish(json.dumps(reply))

    

class ListJupyterDrivesHandler(JupyterDrivesAPIHandler):
    """
    List available drives. Mounts drives.
    """
    def initialize(self, logger: logging.Logger, manager: JupyterDrivesManager):
        return super().initialize(logger, manager)
    
    # Later on, filters can be added for the listing 
    @tornado.web.authenticated
    async def get(self):
        drives = await self._manager.list_drives()
        self.finish(json.dumps(drives))
    
    @tornado.web.authenticated
    async def post(self):
        body = self.get_json_body()
        result = await self._manager.mount_drive(**body)
        self.finish(json.dump(result))

class ContentsJupyterDrivesHandler(JupyterDrivesAPIHandler):
    """
    Deals with contents of a drive.
    """
    @tornado.web.authenticated
    async def get(self):
        body = self.get_json_body()
        contents = await self._manager.get_contents(**body)
        self.finish(json.dump(contents))

default_handlers = [
    ("drives", ListJupyterDrivesHandler),
    ("drives/drive", ContentsJupyterDrivesHandler)
]

def setup_handlers(web_app: tornado.web.Application, config: traitlets.config.Config, log: Optional[logging.Logger] = None):
    host_pattern = ".*$"
    base_url = url_path_join(web_app.settings["base_url"], NAMESPACE)

    log = log or logging.getLogger(__name__)

    provider = DrivesConfig(config=config).provider
    entry_point = MANAGERS.get(provider)
    if entry_point is None:
        log.error(f"JupyterDrives Manager: No manager defined for provider '{provider}'.")
        raise NotImplementedError()
    manager_factory = entry_point.load()
    log.info(f"JupyterDrives Manager Class {manager_factory}")
    try:
        manager = manager_factory(config)
    except Exception as err:
        import traceback
        logging.error("JupyterDrives Manager Exception", exc_info=1)
        raise err

    handlers = [
        (
            url_path_join(base_url, pattern),
            handler,
            {"logger": log, "manager": manager}
        )
        for pattern, handler in default_handlers
    ]

    log.debug(f"Jupyter-Drives Handlers: {handlers}")

    web_app.add_handlers(host_pattern, handlers)
