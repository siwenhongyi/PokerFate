from pf_intercept.proxy import (
    ProbedRoute,
    ServerRouteCandidate,
    _choose_probed_route,
    _parse_server_route_candidates,
)


def _candidate(mode: str, host: str, port: int = 9012) -> ServerRouteCandidate:
    return ServerRouteCandidate(
        mode=mode,
        server_host=f"wss://{host}:{port}",
        wss_host=host,
        wss_port=port,
        http_scheme="http",
        http_host=host,
        http_port=8888,
    )


def test_parse_server_route_candidates_excludes_wss_443():
    data = {
        "server": {
            "server": [
                {
                    "http_host": "http://121.196.174.32:8888/",
                    "server_host": "wss://121.196.174.32:9013",
                },
                {
                    "http_host": "https://ga-foreign.poker-fate.com/",
                    "server_host": "wss://ga-foreign.poker-fate.com:9012",
                },
                {
                    "http_host": "https://awsb-entry.poker-fate.com/",
                    "server_host": "wss://awss-entry.poker-fate.net:443",
                },
            ]
        }
    }

    routes = _parse_server_route_candidates(data, "ga-foreign.poker-fate.com")

    assert [(r.mode, r.wss_host, r.wss_port) for r in routes] == [
        ("ip", "121.196.174.32", 9013),
        ("host", "ga-foreign.poker-fate.com", 9012),
    ]


def test_choose_host_route_when_domain_latency_is_fast_enough():
    host = ProbedRoute(_candidate("host", "ga-foreign.poker-fate.com"), "47.57.185.249", 80.0)
    ip = ProbedRoute(_candidate("ip", "121.196.174.32", 9013), "121.196.174.32", 30.0)

    assert _choose_probed_route([ip, host]) is host


def test_choose_fastest_route_when_domain_latency_is_slow():
    host = ProbedRoute(_candidate("host", "ga-foreign.poker-fate.com"), "47.57.185.249", 220.0)
    ip = ProbedRoute(_candidate("ip", "121.196.174.32", 9013), "121.196.174.32", 70.0)

    assert _choose_probed_route([host, ip]) is ip
