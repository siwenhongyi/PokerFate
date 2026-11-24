import sys
from dataclasses import asdict
import pytest
from pf_intercept.options import RunOptions
from pf_intercept.headless.__main__ import _parse_args
from pf_intercept.proxy.app import _parse_proxy_args


@pytest.mark.parametrize('argv', [[], ['--bb','5000','--buyin-bb','80','--max-auto-rebuy','5',
    '--profit-lock-bb','140','--topup-below-bb','0','--stakes','5000,1000', '--web-port','9999',
    '--no-web','--no-remote-live','--no-notify','--no-auto-rewards','--no-task-hands','--verbose']])
def test_modes_share_names_and_defaults(monkeypatch, argv):
    monkeypatch.setattr(sys, 'argv', ['headless', *argv])
    assert RunOptions.from_namespace(_parse_args()) == RunOptions.from_namespace(_parse_proxy_args(argv))


@pytest.mark.parametrize('argv', [['--max-auto-rebuy','-1'],['--max-auto-rebuy','21'],
                                ['--topup-below-bb','-1'], ['--buyin-bb','0'],['--stakes','777']])
def test_modes_reject_invalid_values_the_same_way(monkeypatch, argv):
    monkeypatch.setattr(sys, 'argv', ['headless', *argv])
    with pytest.raises(SystemExit) as h:
        _parse_args()
    with pytest.raises(SystemExit) as p:
        _parse_proxy_args(argv)
    assert h.value.code == p.value.code == 2


def test_removed_config_constants():
    from pf_intercept import config
    for name in ['ENTERTAINMENT_WEB_HOST','ENTERTAINMENT_WEB_PORT','PROFIT_LOCK_BB_THRESHOLD',
                 'TOPUP_BELOW_BB','TOPUP_TARGET_BB']:
        assert not hasattr(config, name)


def test_launcher_stop_does_not_start_helpers(monkeypatch):
    from pf_intercept import launcher
    from pf_intercept.proxy import app
    monkeypatch.setattr(sys, 'argv', ['launcher','--stop'])
    monkeypatch.setattr(app, 'request_stop', lambda _: None)
    monkeypatch.setattr(launcher, '_start_mitmweb', lambda: pytest.fail('must not launch'))
    monkeypatch.setattr(launcher, '_start_dns_elevated', lambda: pytest.fail('must not launch'))
    assert launcher.main() == 0


def test_launcher_mitmweb_captures_the_login_before_rewriting_it(monkeypatch, tmp_path):
    from pf_intercept import launcher
    started = {}

    class FakePopen:
        pid = 1

        def __init__(self, cmd, **kwargs):
            started['cmd'] = cmd

    monkeypatch.setattr(launcher.shutil, 'which', lambda name: '/bin/mitmweb')
    monkeypatch.setattr(launcher.subprocess, 'Popen', FakePopen)
    monkeypatch.setattr(launcher, '_PROJECT_ROOT', tmp_path)
    launcher._start_mitmweb()
    scripts = [started['cmd'][i + 1] for i, arg in enumerate(started['cmd']) if arg == '-s']
    assert scripts == [str(launcher._CAPTURE_LOGIN_SCRIPT), str(launcher._FORCE_DOMAIN_SCRIPT)]
