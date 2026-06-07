import pytest
from src.admin.application.use_cases.authenticate_user import AuthenticateUser, ChangePassword, RequestPasswordReset, ResetPasswordWithCode
from src.admin.domain.entities.user import User
from src.admin.domain.exceptions import AuthError
from src.admin.domain.ports.password_reset_repository import PasswordResetRecord
from tests.unit.conftest import AsyncRepo, Hasher, Tokens, now
from datetime import timedelta

@pytest.mark.asyncio
async def test_login_returns_token_and_preserves_member_permissions():
    user = User.create_member(id="u", email="m@a.com", password_hash="hash:secret123", tenant_id="t", permissions=["routes"], now=now())
    uc = AuthenticateUser(AsyncRepo(u=user), Hasher(), Tokens())
    token, returned = await uc.login(" M@A.COM ", "secret123")
    assert returned is user and "routes" in token

@pytest.mark.asyncio
async def test_login_rejects_unknown_or_bad_password():
    uc = AuthenticateUser(AsyncRepo(), Hasher(), Tokens())
    with pytest.raises(AuthError): await uc.login("x@y.com", "bad")

@pytest.mark.asyncio
async def test_change_password_validates_current_password_and_updates_hash():
    user = User.create_admin(id="u", email="u@a.com", password_hash="hash:oldpass1", tenant_id="t", now=now())
    repo = AsyncRepo(u=user)
    await ChangePassword(repo, Hasher()).execute("u", "oldpass1", "newpass1")
    assert repo.saved[-1].password_hash == "hash:newpass1"
    with pytest.raises(AuthError): await ChangePassword(repo, Hasher()).execute("u", "wrong", "newpass1")

class ResetRepo:
    def __init__(self): self.record=None; self.cleared=[]
    async def save(self, record): self.record=record
    async def get_for_email(self, email): return self.record if self.record and self.record.email==email else None
    async def clear(self, email): self.cleared.append(email); self.record=None
class EmailSender:
    def __init__(self): self.sent=[]
    async def send_verification_code(self, email, code): self.sent.append((email, code))

@pytest.mark.asyncio
async def test_password_reset_is_uniform_and_successfully_resets_with_code(monkeypatch):
    user = User.create_admin(id="u", email="u@a.com", password_hash="hash:oldpass1", tenant_id="t", now=now())
    users = AsyncRepo(u=user); resets=ResetRepo(); sender=EmailSender()
    monkeypatch.setattr("secrets.randbelow", lambda n: 123456)
    await RequestPasswordReset(users, resets, sender).execute("u@a.com")
    assert sender.sent == [("u@a.com", "123456")]
    await ResetPasswordWithCode(users, resets, Hasher()).execute("u@a.com", "123456", "newpass1")
    assert users.saved[-1].password_hash == "hash:newpass1"
    assert resets.cleared == ["u@a.com"]

@pytest.mark.asyncio
async def test_expired_or_invalid_reset_code_is_rejected():
    import hashlib
    user = User.create_admin(id="u", email="u@a.com", password_hash="hash:oldpass1", tenant_id="t", now=now())
    resets=ResetRepo(); resets.record=PasswordResetRecord(email="u@a.com", code_hash=hashlib.sha256(b"111111").hexdigest(), expires_at=now()-timedelta(minutes=1))
    with pytest.raises(AuthError): await ResetPasswordWithCode(AsyncRepo(u=user), resets, Hasher()).execute("u@a.com", "111111", "newpass1")
