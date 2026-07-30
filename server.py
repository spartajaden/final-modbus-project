"""HTTP API server for the Factory I/O Modbus process.

Run with:
    python server.py

Factory I/O must be in RUN mode with the Modbus TCP/IP Server driver enabled.
"""

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import importlib.util
import json
import mimetypes
from pathlib import Path
import socket
import threading
import traceback
from urllib.parse import unquote, urlparse


HOST = "0.0.0.0"
PORT = 9000
BASE_DIR = Path(__file__).resolve().parent
WEB_DIR = BASE_DIR / "web"

CONTROL_LOCK = threading.Lock()


def load_process_module():
    module_path = Path(__file__).with_name("pyfa-project.py")
    spec = importlib.util.spec_from_file_location("factory_process_control", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load {module_path}")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


process = load_process_module()


def thread_alive(thread):
    return bool(thread and thread.is_alive())


def build_status():
    return {
        "server_running": True,
        "connected": bool(process.connected),
        "running": bool(process.process_run),
        "counts": {
            "blue": process.blue_material_count,
            "green": process.green_material_count,
        },
        "threads": {
            "production": thread_alive(process.production_thread),
            "sorting": thread_alive(process.sorting_thread),
            "modbus_record": thread_alive(process.modbus_record_thread),
        },
        "modbus_record_file": process.current_modbus_record_file,
        "target": {
            "ip_address": process.IP_ADDRESS,
            "port": process.PORT,
            "unit_id": process.UNIT_ID,
        },
    }


def read_snapshot():
    status = build_status()
    if not status["connected"]:
        return {
            "status": status,
            "modbus": None,
        }

    return {
        "status": status,
        "modbus": process.read_modbus_snapshot(),
    }


def list_record_files():
    files = sorted(
        BASE_DIR.glob("modbus_records*.csv"),
        key=lambda file_path: file_path.stat().st_mtime,
        reverse=True,
    )
    return [
        {
            "name": file_path.name,
            "size": file_path.stat().st_size,
            "modified": file_path.stat().st_mtime,
        }
        for file_path in files
    ]


def find_record_file(name):
    requested = Path(unquote(name)).name
    if not requested.startswith("modbus_records") or not requested.endswith(".csv"):
        return None

    file_path = (BASE_DIR / requested).resolve()
    if BASE_DIR not in file_path.parents and file_path != BASE_DIR:
        return None
    if not file_path.exists() or not file_path.is_file():
        return None
    return file_path


def disconnect_factory_io():
    if process.process_run:
        process.stop_all()

    try:
        process.client.close()
    finally:
        process.connected = False

    return build_status()


def create_record_file():
    if not process.MODBUS_RECORD_ENABLED:
        raise RuntimeError("Modbus record is disabled")

    now = process.tt.time()
    with process.modbus_record_lock:
        process.modbus_record_file_started_at = now
        process.current_modbus_record_file = process.make_modbus_record_filename(now)
        process.write_modbus_record_header(process.current_modbus_record_file)

    return {
        "name": Path(process.current_modbus_record_file).name,
        "status": build_status(),
    }


def delete_record_file(name):
    file_path = find_record_file(name)
    if file_path is None:
        return None

    active_file = (BASE_DIR / Path(process.current_modbus_record_file).name).resolve()
    if file_path == active_file and process.process_run:
        raise RuntimeError("Cannot delete the active CSV while the process is running")

    file_path.unlink()
    if file_path == active_file:
        process.current_modbus_record_file = process.MODBUS_RECORD_FILE
        process.modbus_record_file_started_at = 0.0

    return {"deleted": file_path.name}


def prepare_server_shutdown():
    try:
        process.stop_all()
    except Exception as exc:
        print("Stop before web server shutdown skipped:", exc)

    try:
        process.client.close()
    except Exception as exc:
        print("Client close before web server shutdown skipped:", exc)
    finally:
        process.connected = False

    return {
        "server_running": False,
        "shutdown": True,
        "message": "웹 서버를 종료합니다.",
    }


class RequestHandler(BaseHTTPRequestHandler):
    server_version = "FactoryIOServer/1.0"

    def do_HEAD(self):
        path = urlparse(self.path).path
        if path == "/" or path == "/index.html":
            self.send_static_head(WEB_DIR / "index.html")
            return
        if path.startswith("/static/"):
            self.send_static_head(WEB_DIR / path.removeprefix("/static/"))
            return
        self.send_response(404)
        self.end_headers()

    def do_GET(self):
        path = urlparse(self.path).path

        if path == "/" or path == "/index.html":
            self.send_static_file(WEB_DIR / "index.html")
            return

        if path == "/api/status" or path == "/status":
            self.send_json(build_status())
            return

        if path == "/api/snapshot" or path == "/snapshot":
            try:
                self.send_json(read_snapshot())
            except Exception as exc:
                self.send_json(
                    {
                        "error": str(exc),
                        "status": build_status(),
                    },
                    status=503,
                )
            return

        if path == "/api/records":
            self.send_json({"files": list_record_files()})
            return

        if path == "/api/records/latest":
            files = list_record_files()
            if not files:
                self.send_json({"error": "CSV record file not found"}, status=404)
                return
            self.send_record_file(files[0]["name"])
            return

        if path.startswith("/api/records/"):
            self.send_record_file(path.removeprefix("/api/records/"))
            return

        if path.startswith("/static/"):
            static_path = WEB_DIR / path.removeprefix("/static/")
            self.send_static_file(static_path)
            return

        self.send_json({"error": "not found"}, status=404)

    def do_POST(self):
        path = urlparse(self.path).path

        try:
            if path == "/api/connect" or path == "/connect":
                try:
                    with CONTROL_LOCK:
                        process.ensure_factory_io_connected()
                    self.send_json(build_status())
                except Exception:
                    self.send_json(
                        {
                            "error": "서버가 꺼져 있습니다.",
                            "code": "factory_io_server_off",
                            "status": build_status(),
                        },
                        status=503,
                    )
                return

            if path == "/api/disconnect" or path == "/disconnect":
                with CONTROL_LOCK:
                    status = disconnect_factory_io()
                self.send_json(status)
                return

            if path == "/api/start" or path == "/start":
                with CONTROL_LOCK:
                    process.auto_start_factory_io(reset_outputs=True)
                self.send_json(build_status())
                return

            if path == "/api/stop" or path == "/stop":
                with CONTROL_LOCK:
                    process.stop_all()
                self.send_json(build_status())
                return

            if path == "/api/records/new":
                with CONTROL_LOCK:
                    payload = create_record_file()
                self.send_json(payload)
                return

            if path == "/api/shutdown":
                with CONTROL_LOCK:
                    payload = prepare_server_shutdown()
                self.send_json(payload)
                threading.Thread(target=self.server.shutdown, daemon=True).start()
                return

            self.send_json({"error": "not found"}, status=404)
        except Exception as exc:
            self.send_json(
                {
                    "error": str(exc),
                    "traceback": traceback.format_exc(),
                },
                status=500,
            )

    def do_DELETE(self):
        path = urlparse(self.path).path

        try:
            if path.startswith("/api/records/"):
                with CONTROL_LOCK:
                    payload = delete_record_file(path.removeprefix("/api/records/"))
                if payload is None:
                    self.send_json({"error": "CSV record file not found"}, status=404)
                    return
                self.send_json(payload)
                return

            self.send_json({"error": "not found"}, status=404)
        except Exception as exc:
            self.send_json(
                {
                    "error": str(exc),
                    "traceback": traceback.format_exc(),
                },
                status=500,
            )

    def log_message(self, format, *args):
        print("%s - %s" % (self.address_string(), format % args))

    def send_json(self, payload, status=200):
        data = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_no_cache_headers()
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def send_static_file(self, file_path):
        file_path = file_path.resolve()
        if WEB_DIR not in file_path.parents and file_path != WEB_DIR:
            self.send_json({"error": "not found"}, status=404)
            return
        if not file_path.exists() or not file_path.is_file():
            self.send_json({"error": "not found"}, status=404)
            return

        content_type = mimetypes.guess_type(file_path.name)[0] or "application/octet-stream"
        data = file_path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_no_cache_headers()
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def send_static_head(self, file_path):
        file_path = file_path.resolve()
        if WEB_DIR not in file_path.parents and file_path != WEB_DIR:
            self.send_response(404)
            self.end_headers()
            return
        if not file_path.exists() or not file_path.is_file():
            self.send_response(404)
            self.end_headers()
            return

        content_type = mimetypes.guess_type(file_path.name)[0] or "application/octet-stream"
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_no_cache_headers()
        self.send_header("Content-Length", str(file_path.stat().st_size))
        self.end_headers()

    def send_record_file(self, name):
        file_path = find_record_file(name)
        if file_path is None:
            self.send_json({"error": "CSV record file not found"}, status=404)
            return

        data = file_path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", "text/csv; charset=utf-8")
        self.send_header("Content-Disposition", f'attachment; filename="{file_path.name}"')
        self.send_no_cache_headers()
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def send_no_cache_headers(self):
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")


def main():
    server = ThreadingHTTPServer((HOST, PORT), RequestHandler)
    local_ip = socket.gethostbyname(socket.gethostname())
    print(f"Factory I/O control server listening on http://127.0.0.1:{PORT}")
    print(f"Network URL: http://{local_ip}:{PORT}")
    print("Use Ctrl+C to stop the server. If the process is running, outputs will be stopped safely.")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("Stopping server")
    finally:
        try:
            try:
                process.stop_all()
            except Exception as exc:
                print("Stop during shutdown skipped:", exc)
        finally:
            try:
                process.client.close()
            except Exception:
                pass
            server.server_close()


if __name__ == "__main__":
    main()
