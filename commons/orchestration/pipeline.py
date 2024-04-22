import sys
import time
from collections.abc import Callable
from threading import Thread
from typing import Optional, Dict, Any

import requests
from flask import Flask, make_response, request
from werkzeug.serving import make_server, BaseWSGIServer


class AbstractScript:
    def __init__(self):
        self._execution_complete_callback: Optional[Callable] = None
        self._should_stop: bool = False

        self.iteration: int = 0

    def start(self):
        """ Starts the script execution loop """
        async_thread = Thread(target=self._start, daemon=True)
        async_thread.start()

    def _start(self):
        # Wait for the server to start
        time.sleep(5)

        while not self._should_stop:
            self.run_batch()
            self.update_batch_status()
            self.iteration += 1

            # Sleep for a bit to avoid overloading the server
            time.sleep(0.1)

        # Call the completion callback
        self._on_complete()

    def run_batch(self):
        """ Processes the next batch of data, called in a loop until the script is stopped """
        raise NotImplementedError

    def update_batch_status(self):
        """ Updates the batch status to the backend, called automatically after each batch is processed """
        raise NotImplementedError

    def get_status(self) -> Dict[str, Any]:
        """ Can be called by the orchestrator to get the current status of the script """
        raise NotImplementedError

    def schedule_stop(self):
        """ Flag set by the script to stop processing after the current batch """
        self._should_stop = True

    def set_execution_complete_callback(self, callback: Callable):
        """ Sets the callback method when the script execution is complete """
        self._execution_complete_callback = callback

    def _on_complete(self):
        """ Calls the execution complete callback """
        if self._execution_complete_callback is not None:
            self._execution_complete_callback()


class AbstractPipelineShutdownCallback:
    def execute(self, container_id: str, container_port: int):
        raise NotImplementedError


class DummyPipelineShutdownCallback(AbstractPipelineShutdownCallback):
    def execute(self, container_id: str, container_port: int):
        print(f"Shutting down pipeline at {container_id}:{container_port}")


class BackendPipelineShutdownCallback(AbstractPipelineShutdownCallback):
    def execute(self, container_id: str, container_port: int):
        try:
            requests.delete(f"http://orchestrator:5000/pipelines/status/{container_id}")
            time.sleep(3)
        except Exception as e:
            print(f"Failed to send pipeline shutdown signal to backend: {e}", file=sys.stderr)


class Pipeline(Thread):
    def __init__(self, container_id: str, container_port: int, script: AbstractScript, shutdown_callback: AbstractPipelineShutdownCallback):
        super().__init__(daemon=False)
        self.container_id: str = container_id
        self.container_port: int = container_port

        # Pipeline script to run
        self.script: AbstractScript = script
        self.script.set_execution_complete_callback(self.shutdown)

        # Callback to call when the pipeline is complete
        self.shutdown_callback: AbstractPipelineShutdownCallback = shutdown_callback

        # Flask server to handle API requests
        self.flask_app: Flask = Flask(__name__)
        self._setup_routes()
        self.server: BaseWSGIServer = make_server("0.0.0.0", self.container_port, self.flask_app)

    def _setup_routes(self):
        @self.flask_app.route("/control", methods=["POST"])
        def control_pipeline():
            body = request.get_json()
            action = body.get("action")
            if action != "stop":
                return make_response({"error": "Invalid action"}, 400)

            self.stop_script()
            return make_response({"message": "Successfully set stop-script flag"}, 200)

        @self.flask_app.route("/status", methods=["GET"])
        def get_status():
            status = self.script.get_status()
            return make_response({
                "message": "OK",
                "status": status
            }, 200)

    def run(self):
        """ Starts the pipeline server and script execution """
        # Start the script execution
        print("Starting pipeline script...")
        self.script.start()
        time.sleep(1)

        print("Starting pipeline server...")
        self.server.serve_forever()

    def stop_script(self):
        """ Signals the script to stop processing and exit after the current batch """
        print("Stopping pipeline script...")
        self.script.schedule_stop()

    def shutdown(self):
        """ Stop the pipeline server, called when the script execution is complete """
        print("Stopping pipeline server...")

        # Send pipeline shutdown signal to backend
        self.shutdown_callback.execute(self.container_id, self.container_port)

        # Stop the pipeline server
        self.server.shutdown()
        print("See you later!")


if __name__ == "__main__":
    class DummyScript(AbstractScript):
        def run_batch(self):
            print(f"Running batch #{self.iteration}")
            time.sleep(2)

        def update_batch_status(self):
            print(f"Updating status for batch #{self.iteration}")
            time.sleep(2)

        def get_status(self) -> Dict[str, Any]:
            return {
                "iteration": self.iteration
            }


    class DummyPipelineShutdownCallback(AbstractPipelineShutdownCallback):
        def execute(self, container_id: str, container_port: int):
            print(f"Shutting down pipeline at {container_id}:{container_port}")


    # Example usage
    container_id = "test_container"
    container_port = 5578

    script = DummyScript()
    shutdown_callback = DummyPipelineShutdownCallback()

    pipeline = Pipeline(container_id, container_port, script, shutdown_callback)
    pipeline.start()
