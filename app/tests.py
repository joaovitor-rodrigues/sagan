"""Testes do SAGAN.

As chamadas externas (ExoFOP e MAST/lightkurve) são substituídas por dados
sintéticos, então a suíte roda offline:  python manage.py test
"""
import json
from unittest import mock

import numpy as np
import pandas as pd
from django.test import SimpleTestCase
from django.urls import reverse
from lightkurve import LightCurve

from . import lightcurves, views

TIC = 231663901


def fake_toi_dataframe():
    return pd.DataFrame([
        {"tic_id": 231663901, "toi": 101.01, "disposition": "KP", "source": "spoc",
         "period": 1.43, "stellar_radius": 0.89, "stellar_mass": 1.05,
         "alerted": "2018-09-05", "updated": "2021-10-07", "modified": "2021-10-29",
         "comments": "WASP-46 b"},
        {"tic_id": 149603524, "toi": 102.01, "disposition": "PC", "source": "qlp",
         "period": 4.41, "stellar_radius": 1.21, "stellar_mass": 1.28,
         "alerted": "2019-05-07", "updated": "2021-08-24", "modified": "2021-10-29",
         "comments": "WASP 62 b"},
        {"tic_id": 336732616, "toi": 103.01, "disposition": "FP", "source": "spoc",
         "period": 3.55, "stellar_radius": 1.40, "stellar_mass": 1.10,
         "alerted": "2018-09-05", "updated": "2020-01-01", "modified": "2021-10-29",
         "comments": ""},
    ])


def fake_lightcurve(n=2000, period=3.0):
    """Curva de luz sintética com um trânsito periódico."""
    rng = np.random.default_rng(42)
    time = np.linspace(1325.0, 1352.0, n)
    flux = 1000 + rng.normal(0, 1, n)
    phase = ((time - 1326.0) % period) / period
    flux[(phase < 0.02) | (phase > 0.98)] -= 10
    return LightCurve(time=time, flux=flux)


class FakeSearchResult:
    def __init__(self):
        self.table = mock.Mock()
        self.table.to_pandas.return_value = pd.DataFrame([
            {"mission": "TESS Sector 01", "year": 2018, "author": "SPOC"},
            {"mission": "TESS Sector 02", "year": 2018, "author": "QLP"},
        ])

    def __len__(self):
        return 2

    def __getitem__(self, ind):
        item = mock.Mock()
        item.download.return_value = fake_lightcurve()
        return item


@mock.patch("app.views.get_toi_dataframe", side_effect=fake_toi_dataframe)
class StaticPagesTests(SimpleTestCase):
    def test_root_redirects_to_app(self, _):
        resp = self.client.get("/")
        self.assertRedirects(resp, "/app/")

    def test_theory_and_about_citations(self, _):
        import re
        for name in ("theory", "about"):
            with self.subTest(page=name):
                html = self.client.get(reverse(name)).content.decode()
                anchors = set(re.findall(r'id="(ref-[a-z0-9]+)"', html))
                cited = set(re.findall(r'href="#(ref-[a-z0-9]+)"', html))
                self.assertTrue(cited)
                self.assertEqual(cited - anchors, set(), "citação sem referência")
                self.assertEqual(anchors - cited, set(), "referência nunca citada")
                self.assertIn('class="sg-chart', html)

    def test_pages_render(self, _):
        for name in ("index", "about", "tutorial", "theory"):
            with self.subTest(page=name):
                self.assertEqual(self.client.get(reverse(name)).status_code, 200)


@mock.patch("app.views.get_toi_dataframe", side_effect=fake_toi_dataframe)
class ObjectListTests(SimpleTestCase):
    def test_list_renders_all(self, _):
        resp = self.client.get(reverse("list"))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.context["total_count"], 3)

    def test_search(self, _):
        resp = self.client.get(reverse("list"), {"q": "WASP-46"})
        self.assertEqual(resp.context["total_count"], 1)

    def test_filter_disposition(self, _):
        resp = self.client.get(reverse("list"), {"disposition": "PC"})
        self.assertEqual([r["tic_id"] for r in resp.context["page_obj"]], [149603524])

    def test_order_numeric_desc(self, _):
        resp = self.client.get(reverse("list"), {"order_by": "period", "order_dir": "desc"})
        periods = [r["period"] for r in resp.context["page_obj"]]
        self.assertEqual(periods, sorted(periods, reverse=True))

    def test_search_with_regex_characters(self, _):
        resp = self.client.get(reverse("list"), {"q": "WASP-46 ("})
        self.assertEqual(resp.status_code, 200)

    def test_catalog_unavailable(self, mocked):
        mocked.side_effect = RuntimeError("offline")
        self.assertEqual(self.client.get(reverse("list")).status_code, 502)


def _clear_caches():
    lightcurves.search.cache_clear()
    lightcurves.get_base_lightcurve.cache_clear()


@mock.patch("lightkurve.search_lightcurve", return_value=FakeSearchResult())
class LightCurveTests(SimpleTestCase):
    def setUp(self):
        _clear_caches()

    def process(self, pipeline, ind=0):
        resp = self.client.post(
            reverse("lc_process", args=[TIC, ind]),
            {"pipeline": json.dumps(pipeline)},
        )
        return resp, json.loads(resp.content)

    def test_modal_lists_observations(self, _):
        resp = self.client.post(reverse("modal"), {"id": str(TIC)})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.context["d"]), 2)

    def test_modal_rejects_invalid_id(self, _):
        self.assertEqual(self.client.post(reverse("modal"), {"id": "abc"}).status_code, 400)

    def test_object_page(self, _):
        resp = self.client.get(reverse("object", args=[TIC, 0]))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.context["pipeline_json"], "[]")
        self.assertEqual(len(resp.context["x"]), len(resp.context["base_x"]))

    def test_object_out_of_range(self, _):
        self.assertEqual(self.client.get(reverse("object", args=[TIC, 99])).status_code, 404)

    def test_folded_page_starts_with_fold_step(self, _):
        resp = self.client.get(reverse("folded", args=[TIC, 0]))
        self.assertEqual(resp.status_code, 200)
        pipeline = json.loads(resp.context["pipeline_json"])
        self.assertEqual(pipeline[0]["name"], "fold")
        # A curva sintética tem trânsitos a cada 3 dias
        self.assertAlmostEqual(pipeline[0]["params"]["period"], 3.0, delta=0.05)
        # ...e o T0 encontrado centraliza o trânsito na fase 0
        x, y = resp.context["x"], resp.context["y"]
        dip_phase = x[min(range(len(y)), key=lambda i: y[i] if y[i] is not None else 9e9)]
        self.assertLess(abs(dip_phase), 0.1)

    def test_param_inputs_use_decimal_point(self, _):
        html = self.client.get(reverse("object", args=[TIC, 0])).content.decode()
        self.assertIn('value="0.02"', html)
        self.assertIn('step="0.001"', html)
        self.assertNotIn('value="0,02"', html)

    def test_light_curve_downloaded_once(self, search_mock):
        self.client.get(reverse("object", args=[TIC, 0]))
        self.process([{"name": "bin", "params": {"time_bin_size": "0.05"}}])
        self.assertEqual(search_mock.call_count, 1)

    def test_every_function_applies(self, _):
        params = {
            "flatten": {"window_length": "101", "polyorder": "2"},
            "fold": {"period": "3.0"},
            "bin": {"time_bin_size": "0.02"},
            "remove_outliers": {"sigma": "5"},
            "smooth": {"filter_width": "11"},
            "normalize": {"unit": "ppm"},
            "truncate": {"before": "1330", "after": "1340"},
        }
        self.assertEqual(set(params), set(views.LC_FUNCTIONS))
        for name, p in params.items():
            with self.subTest(function=name):
                resp, data = self.process([{"name": name, "params": p}])
                self.assertEqual(resp.status_code, 200, data)
                self.assertEqual(len(data["x"]), len(data["y"]))
                self.assertEqual(data["functions"][0]["name"], name)

    def test_chained_pipeline(self, _):
        resp, data = self.process([
            {"name": "remove_outliers", "params": {"sigma": 5}},
            {"name": "flatten", "params": {}},
            {"name": "fold", "params": {"period": 3}},
            {"name": "bin", "params": {"time_bin_size": 0.01}},
        ])
        self.assertEqual(resp.status_code, 200, data)
        self.assertEqual(len(data["functions"]), 4)
        self.assertIn("Fase", data["x_label"])

    def test_empty_pipeline_returns_base(self, _):
        resp, data = self.process([])
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(data["functions"], [])

    def test_invalid_function(self, _):
        resp, _ = self.process([{"name": "rm -rf", "params": {}}])
        self.assertEqual(resp.status_code, 400)

    def test_invalid_param_value(self, _):
        resp, data = self.process([{"name": "remove_outliers", "params": {"sigma": "abc"}}])
        self.assertEqual(resp.status_code, 400)
        resp, data = self.process([{"name": "normalize", "params": {"unit": "<script>"}}])
        self.assertEqual(resp.status_code, 400)

    def test_unknown_params_are_dropped(self, _):
        resp, data = self.process([{"name": "bin", "params": {"time_bin_size": 0.05, "evil": "x"}}])
        self.assertEqual(data["functions"][0]["params"], {"time_bin_size": 0.05})

    def test_fold_requires_period(self, _):
        resp, data = self.process([{"name": "fold", "params": {}}])
        self.assertEqual(resp.status_code, 400)
        self.assertIn("obrigatório", data["error"])

    def test_malformed_json(self, _):
        resp = self.client.post(reverse("lc_process", args=[TIC, 0]), {"pipeline": "{nope"})
        self.assertEqual(resp.status_code, 400)

    def test_pipeline_length_limit(self, _):
        resp, _ = self.process([{"name": "bin", "params": {}}] * 21)
        self.assertEqual(resp.status_code, 400)

    def test_process_requires_post(self, _):
        resp = self.client.get(reverse("lc_process", args=[TIC, 0]))
        self.assertEqual(resp.status_code, 405)

    def test_csrf_enforced(self, _):
        from django.test import Client
        client = Client(enforce_csrf_checks=True)
        resp = client.post(reverse("lc_process", args=[TIC, 0]), {"pipeline": "[]"})
        self.assertEqual(resp.status_code, 403)
