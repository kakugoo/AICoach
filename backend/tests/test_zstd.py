import pytest
import zstandard
from test_auth import register

from app.core.config import get_settings
from app.modules.demos.decompress import InvalidDemoArchive, decompress_demo


@pytest.fixture(autouse=True)
def isolated_storage(tmp_path, monkeypatch):
    monkeypatch.setattr(get_settings(), "demo_storage_dir", str(tmp_path / "storage"))
    monkeypatch.setattr(get_settings(), "demo_max_bytes", 4096)
    monkeypatch.setattr(get_settings(), "demo_quota_bytes", 8192)


def test_zstd_upload_and_bounded_decode(client, tmp_path):
    data = b"PBDEMS2\x00" + b"x" * 1000
    blob = zstandard.ZstdCompressor().compress(data)
    src, dest = tmp_path / "fixture.dem.zst", tmp_path / "output.dem"
    src.write_bytes(blob)
    assert decompress_demo(src, dest, len(data)) == len(data)
    assert dest.read_bytes() == data
    assert register(client).status_code == 201
    response = client.post("/demos?filename=match.dem.zst", content=blob,
                           headers={"Content-Type": "application/octet-stream"})
    assert response.status_code == 201 and response.json()["status"] == "queued"


def test_zst_extension_requires_zstandard_signature(client):
    assert register(client).status_code == 201
    blob = zstandard.ZstdCompressor().compress(b"PBDEMS2\x00" + b"test")
    assert client.post("/demos?filename=match.zst", content=blob,
                       headers={"Content-Type": "application/octet-stream"}).status_code == 201
    assert client.post("/demos?filename=invalid.zst", content=b"PBDEMS2\x00invalid",
                       headers={"Content-Type": "application/octet-stream"}).status_code == 422


def test_corruption_size_and_signature(tmp_path):
    data = b"PBDEMS2\x00" + b"x" * 1000
    blob = zstandard.ZstdCompressor().compress(data)
    src, dest = tmp_path / "fixture.zst", tmp_path / "out.dem"
    for contents, maximum in [(blob[:-1], 2000), (blob, 10), (zstandard.ZstdCompressor().compress(b"not demo"), 2000), (blob + b"trailing", 2000)]:
        src.write_bytes(contents)
        with pytest.raises((InvalidDemoArchive, zstandard.ZstdError)):
            decompress_demo(src, dest, maximum)
        assert not dest.exists()


def test_extension_mismatch_rejected(client):
    assert register(client).status_code == 201
    blob = zstandard.ZstdCompressor().compress(b"PBDEMS2\x00" + b"test")
    assert client.post("/demos?filename=demo.dem", content=blob, headers={"Content-Type": "application/octet-stream"}).status_code == 422
    assert client.post("/demos?filename=demo.dem.zst", content=b"PBDEMS2\x00fake", headers={"Content-Type": "application/octet-stream"}).status_code == 422


def test_worker_reports_corrupt_archive_and_expansion_limit(client, monkeypatch):
    from test_demos import engine

    from app.modules.demos.worker import run_one

    assert register(client).status_code == 201
    bad = client.post("/demos?filename=broken.dem.zst", content=b"\x28\xb5\x2f\xfd" + b"broken data", headers={"Content-Type": "application/octet-stream"})
    assert bad.status_code == 201
    assert run_one(engine())
    error = client.get(f"/demos/{bad.json()['id']}").json()["demo"]
    assert error["status"] == "failed" and "Архив повреждён" in error["error"]
    monkeypatch.setattr(get_settings(), "demo_max_uncompressed_bytes", 16)
    payload = zstandard.ZstdCompressor().compress(b"PBDEMS2\x00" + b"x" * 1000)
    large = client.post("/demos?filename=large.dem.zst", content=payload, headers={"Content-Type": "application/octet-stream"})
    assert large.status_code == 201
    assert run_one(engine())
    error = client.get(f"/demos/{large.json()['id']}").json()["demo"]
    assert error["status"] == "failed" and "превышает" in error["error"]
    assert not list(__import__("pathlib").Path(get_settings().demo_storage_dir).glob("*.unpacked"))
