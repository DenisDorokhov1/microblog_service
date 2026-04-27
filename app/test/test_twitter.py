import pytest
from app.routes import app


@pytest.mark.asyncio
async def test_get_user_info_success(client, test_user):
    """
    Тест успешного получения информации о пользователе
    """

    response = await client.get(
        f"/api/users/{test_user.id}", headers={"api-key": test_user.api_key}
    )

    assert response.status_code == 200

    data = response.json()
    assert data["result"] is True
    assert data["user"]["name"] == "Denis"
    assert data["user"]["id"] == test_user.id
