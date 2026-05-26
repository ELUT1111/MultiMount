from app.webdav_server.middleware import AccessLogMiddleware


def test_webdav_access_log_middleware_writes_configured_file(tmp_path):
    log_path = tmp_path / "webdav-access.log"

    def app(environ, start_response):
        start_response("204 No Content", [])
        return [b""]

    wrapped = AccessLogMiddleware(app, str(log_path))

    def start_response(_status, _headers, _exc_info=None):
        return None

    result = wrapped(
        {
            "REQUEST_METHOD": "PROPFIND",
            "PATH_INFO": "/mount/file.txt",
            "REMOTE_ADDR": "127.0.0.1",
            "REMOTE_USER": "alice",
        },
        start_response,
    )
    list(result)

    content = log_path.read_text(encoding="utf-8")
    assert "127.0.0.1 [alice] PROPFIND /mount/file.txt -> 204" in content
