"""Testes unitários do RateLimiter."""

from app.core.rate_limiter import RateLimiter


def test_permite_primeira_requisicao():
    rl = RateLimiter(max_requests=5, window_minutes=60)
    assert rl.is_allowed("5511999999999") is True


def test_bloqueia_apos_limite():
    rl = RateLimiter(max_requests=3, window_minutes=60)
    phone = "5511888888888"
    assert rl.is_allowed(phone) is True
    assert rl.is_allowed(phone) is True
    assert rl.is_allowed(phone) is True
    assert rl.is_allowed(phone) is False


def test_phones_diferentes_sao_independentes():
    rl = RateLimiter(max_requests=1, window_minutes=60)
    assert rl.is_allowed("5511111111111") is True
    assert rl.is_allowed("5511111111111") is False
    assert rl.is_allowed("5522222222222") is True


def test_janela_expirada_libera_phone():
    from datetime import datetime, timedelta, timezone

    rl = RateLimiter(max_requests=1, window_minutes=60)
    phone = "5511777777777"
    rl.is_allowed(phone)  # usa o slot

    # Simula timestamp antigo (fora da janela)
    rl.requests[phone] = [datetime.now(timezone.utc) - timedelta(hours=2)]

    assert rl.is_allowed(phone) is True


def test_contador_correto():
    rl = RateLimiter(max_requests=10, window_minutes=60)
    phone = "5511666666666"
    for _ in range(5):
        rl.is_allowed(phone)
    assert len(rl.requests[phone]) == 5
