from pathlib import Path
import pytest
from streamlit.testing.v1 import AppTest


def test_dashboard_render_and_filters():
    if not Path('data/dashboard/driver_metrics.csv').exists():
        pytest.skip('Run pipeline to build dashboard data first')
    app = AppTest.from_file('dashboard/app.py', default_timeout=30).run()
    assert not app.exception
    assert len(app.metric) == 8
    app.selectbox[0].select('KZ').run()
    assert not app.exception
    app.multiselect[0].set_value([]).run()
    assert not app.exception
    assert any('No drivers' in warning.value for warning in app.warning)
