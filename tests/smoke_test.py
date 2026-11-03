"""无网络冒烟测试：python tests/smoke_test.py"""
import json
import sys
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.services.mapdata import (  # noqa: E402
    MAPS,
    get_map_data,
    list_maps,
    map_payload,
)
from app.session import SessionStore  # noqa: E402
from utils.sign import get_sign  # noqa: E402
from utils.track import gen_track_points  # noqa: E402


class MapTests(unittest.TestCase):
    def test_all_maps_load(self):
        self.assertEqual(len(list_maps()), len(MAPS))
        for key in MAPS:
            data = get_map_data(key)
            self.assertTrue(data, f"{key} 地图为空")
            self.assertGreaterEqual(len(data), 2)

    def test_map_graph_integrity(self):
        for key in MAPS:
            data = get_map_data(key)
            ids = {item["id"] for item in data}
            self.assertEqual(len(ids), len(data), f"{key} 存在重复 id")
            for item in data:
                for edge in item["edge"]:
                    self.assertIn(edge, ids, f"{key} 的 edge {edge} 不存在")

    def test_track_generation(self):
        for key in MAPS:
            points = json.loads(gen_track_points(200, key))
            self.assertGreaterEqual(len(points), 2)
            for point in points:
                self.assertEqual(len(point.split("-")), 4, point)


class SchoolMatchTests(unittest.TestCase):
    def test_scyz_by_school_id(self):
        payload = map_payload({"schoolId": 2922, "schoolName": "四川邮电职业技术学院"})
        self.assertTrue(payload["map_matched"])
        self.assertEqual(payload["default_map"], "scyz_jk")
        self.assertEqual([item["key"] for item in payload["maps"]], ["scyz_jk"])

    def test_scyz_by_name_without_id(self):
        payload = map_payload({"schoolName": "四川邮电职业技术学院"})
        self.assertEqual(payload["default_map"], "scyz_jk")

    def test_campus_filter(self):
        payload = map_payload({"schoolName": "成都信息工程大学（龙泉校区）"})
        self.assertTrue(payload["map_matched"])
        self.assertEqual(payload["default_map"], "cuit_lqy")
        self.assertEqual(len(payload["maps"]), 1)

    def test_unknown_school_falls_back(self):
        payload = map_payload({"schoolId": 123456, "schoolName": "某某大学"})
        self.assertFalse(payload["map_matched"])
        self.assertEqual(len(payload["maps"]), len(MAPS))


class SignTests(unittest.TestCase):
    def test_sign_is_deterministic(self):
        first = get_sign({"schoolId": 1}, None)
        second = get_sign({"schoolId": 1}, None)
        self.assertEqual(first, second)
        self.assertEqual(len(first), 32)


class SessionTests(unittest.TestCase):
    def test_isolation_and_destroy(self):
        store = SessionStore(idle_ttl=60, max_ttl=120)
        a = store.create("token-a", {"studentName": "A"})
        b = store.create("token-b", {"studentName": "B"})
        self.assertNotEqual(a.sid, b.sid)
        self.assertEqual(store.get(a.sid).token, "token-a")
        store.destroy(a.sid)
        self.assertIsNone(store.get(a.sid))
        self.assertIsNotNone(store.get(b.sid))
        self.assertEqual(store.count(), 1)

    def test_idle_expiry(self):
        store = SessionStore(idle_ttl=1, max_ttl=60)
        session = store.create("token", {})
        session.last_seen = time.time() - 5
        self.assertIsNone(store.get(session.sid))


class AppImportTests(unittest.TestCase):
    def test_web_app_imports(self):
        from web.main import app

        paths = {route.path for route in app.routes}
        self.assertIn("/api/login", paths)
        self.assertIn("/api/run", paths)
        self.assertIn("/api/logout", paths)
        self.assertIn("/healthz", paths)


if __name__ == "__main__":
    unittest.main(verbosity=2)
