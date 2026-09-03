"""
Tests for Mergington High School Activities API

This module contains comprehensive tests for all API endpoints, including:
- Happy paths (success cases)
- Error handling (404s, 400s)
- Data integrity and edge cases
"""

import copy
import pytest
from fastapi.testclient import TestClient
from src.app import app, activities


@pytest.fixture
def client():
    """Create a TestClient for the FastAPI app."""
    return TestClient(app)


@pytest.fixture
def fresh_activities(monkeypatch):
    """
    Fixture that provides fresh activities data for each test.
    Resets the activities dict to initial state to avoid cross-test pollution.
    """
    # Store original activities
    original_activities = copy.deepcopy(activities)
    
    # Provide the fresh copy to tests via monkeypatch
    monkeypatch.setattr("src.app.activities", copy.deepcopy(original_activities))
    
    yield
    
    # Restore original activities after test
    monkeypatch.setattr("src.app.activities", original_activities)


@pytest.fixture
def sample_emails():
    """Provide sample email addresses for testing."""
    return {
        "new_student": "alice@mergington.edu",
        "another_student": "bob@mergington.edu",
        "existing_participant": "michael@mergington.edu",  # In Chess Club
    }


# ===========================
# GET /activities Tests
# ===========================

def test_get_activities_returns_all_activities(client, fresh_activities):
    """Test that GET /activities returns all activities with correct structure."""
    response = client.get("/activities")
    
    assert response.status_code == 200
    data = response.json()
    
    # Verify we have 9 activities
    assert len(data) == 9
    
    # Verify required keys in each activity
    for activity_name, activity_data in data.items():
        assert "description" in activity_data
        assert "schedule" in activity_data
        assert "max_participants" in activity_data
        assert "participants" in activity_data
        assert isinstance(activity_data["participants"], list)


def test_get_activities_contains_expected_activities(client, fresh_activities):
    """Test that GET /activities returns known activities."""
    response = client.get("/activities")
    data = response.json()
    
    expected_activities = [
        "Chess Club",
        "Programming Class",
        "Gym Class",
        "Basketball Team",
        "Tennis Club",
        "Art Studio",
        "Music Band",
        "Debate Team",
        "Science Club",
    ]
    
    for activity_name in expected_activities:
        assert activity_name in data


def test_get_activities_chess_club_has_initial_participants(client, fresh_activities):
    """Test that Chess Club has expected initial participants."""
    response = client.get("/activities")
    data = response.json()
    
    chess_club = data["Chess Club"]
    assert len(chess_club["participants"]) == 2
    assert "michael@mergington.edu" in chess_club["participants"]
    assert "daniel@mergington.edu" in chess_club["participants"]


# ===========================
# GET / Redirect Test
# ===========================

def test_root_redirect_to_static(client, fresh_activities):
    """Test that GET / redirects to /static/index.html."""
    response = client.get("/", follow_redirects=False)
    
    assert response.status_code in [307, 302]  # Redirect status codes
    assert response.headers.get("location") == "/static/index.html"


# ===========================
# POST /activities/{activity}/signup Tests - Happy Path
# ===========================

def test_signup_success_new_student(client, fresh_activities, sample_emails):
    """Test successful signup of a new student."""
    activity_name = "Chess Club"
    email = sample_emails["new_student"]
    
    response = client.post(
        f"/activities/{activity_name}/signup",
        params={"email": email}
    )
    
    assert response.status_code == 200
    data = response.json()
    assert "message" in data
    assert email in data["message"]
    assert activity_name in data["message"]


def test_signup_success_participant_added_to_activity(client, fresh_activities, sample_emails):
    """Test that signup actually adds the participant to the activity."""
    activity_name = "Programming Class"
    email = sample_emails["new_student"]
    
    # Get initial count
    initial_response = client.get("/activities")
    initial_count = len(initial_response.json()[activity_name]["participants"])
    
    # Sign up
    response = client.post(
        f"/activities/{activity_name}/signup",
        params={"email": email}
    )
    assert response.status_code == 200
    
    # Verify participant was added
    final_response = client.get("/activities")
    final_count = len(final_response.json()[activity_name]["participants"])
    
    assert final_count == initial_count + 1
    assert email in final_response.json()[activity_name]["participants"]


def test_signup_multiple_students_same_activity(client, fresh_activities, sample_emails):
    """Test that multiple different students can sign up for the same activity."""
    activity_name = "Tennis Club"
    
    # Sign up first student
    response1 = client.post(
        f"/activities/{activity_name}/signup",
        params={"email": sample_emails["new_student"]}
    )
    assert response1.status_code == 200
    
    # Sign up second student
    response2 = client.post(
        f"/activities/{activity_name}/signup",
        params={"email": sample_emails["another_student"]}
    )
    assert response2.status_code == 200
    
    # Verify both are signed up
    final_response = client.get("/activities")
    participants = final_response.json()[activity_name]["participants"]
    
    assert sample_emails["new_student"] in participants
    assert sample_emails["another_student"] in participants


# ===========================
# POST /activities/{activity}/signup Tests - Error Cases
# ===========================

def test_signup_activity_not_found(client, fresh_activities, sample_emails):
    """Test signup to non-existent activity returns 404."""
    response = client.post(
        "/activities/NonExistentClub/signup",
        params={"email": sample_emails["new_student"]}
    )
    
    assert response.status_code == 404
    data = response.json()
    assert "detail" in data


def test_signup_duplicate_student_same_activity(client, fresh_activities, sample_emails):
    """Test that signing up twice for the same activity returns 400."""
    activity_name = "Chess Club"
    email = sample_emails["existing_participant"]  # Already in Chess Club
    
    response = client.post(
        f"/activities/{activity_name}/signup",
        params={"email": email}
    )
    
    assert response.status_code == 400
    data = response.json()
    assert "detail" in data
    assert "already signed up" in data["detail"]


def test_signup_same_student_different_activities_allowed(client, fresh_activities, sample_emails):
    """Test that the same student can sign up for multiple different activities."""
    email = sample_emails["new_student"]
    
    # Sign up for two different activities
    response1 = client.post(
        "/activities/Chess Club/signup",
        params={"email": email}
    )
    response2 = client.post(
        "/activities/Programming Class/signup",
        params={"email": email}
    )
    
    assert response1.status_code == 200
    assert response2.status_code == 200
    
    # Verify student is in both activities
    activities_response = client.get("/activities")
    data = activities_response.json()
    
    assert email in data["Chess Club"]["participants"]
    assert email in data["Programming Class"]["participants"]


# ===========================
# DELETE /activities/{activity}/unregister Tests - Happy Path
# ===========================

def test_unregister_success_existing_participant(client, fresh_activities):
    """Test successful unregistration of an existing participant."""
    activity_name = "Chess Club"
    email = "michael@mergington.edu"  # Existing participant
    
    response = client.delete(
        f"/activities/{activity_name}/unregister",
        params={"email": email}
    )
    
    assert response.status_code == 200
    data = response.json()
    assert "message" in data
    assert email in data["message"]


def test_unregister_success_participant_removed_from_activity(client, fresh_activities):
    """Test that unregister actually removes the participant from the activity."""
    activity_name = "Gym Class"
    email = "john@mergington.edu"  # Existing participant
    
    # Get initial count
    initial_response = client.get("/activities")
    initial_count = len(initial_response.json()[activity_name]["participants"])
    
    # Unregister
    response = client.delete(
        f"/activities/{activity_name}/unregister",
        params={"email": email}
    )
    assert response.status_code == 200
    
    # Verify participant was removed
    final_response = client.get("/activities")
    final_count = len(final_response.json()[activity_name]["participants"])
    
    assert final_count == initial_count - 1
    assert email not in final_response.json()[activity_name]["participants"]


def test_unregister_multiple_participants(client, fresh_activities):
    """Test unregistering multiple participants from the same activity."""
    activity_name = "Art Studio"
    email1 = "maya@mergington.edu"
    email2 = "lucas@mergington.edu"
    
    # Unregister first participant
    response1 = client.delete(
        f"/activities/{activity_name}/unregister",
        params={"email": email1}
    )
    assert response1.status_code == 200
    
    # Unregister second participant
    response2 = client.delete(
        f"/activities/{activity_name}/unregister",
        params={"email": email2}
    )
    assert response2.status_code == 200
    
    # Verify both are removed
    final_response = client.get("/activities")
    participants = final_response.json()[activity_name]["participants"]
    
    assert email1 not in participants
    assert email2 not in participants
    assert len(participants) == 0  # Art Studio should have no participants now


# ===========================
# DELETE /activities/{activity}/unregister Tests - Error Cases
# ===========================

def test_unregister_activity_not_found(client, fresh_activities):
    """Test unregister from non-existent activity returns 404."""
    response = client.delete(
        "/activities/NonExistentClub/unregister",
        params={"email": "student@mergington.edu"}
    )
    
    assert response.status_code == 404
    data = response.json()
    assert "detail" in data


def test_unregister_student_not_enrolled(client, fresh_activities, sample_emails):
    """Test unregistering a student who is not enrolled returns 400."""
    activity_name = "Chess Club"
    email = sample_emails["new_student"]  # Not enrolled in Chess Club
    
    response = client.delete(
        f"/activities/{activity_name}/unregister",
        params={"email": email}
    )
    
    assert response.status_code == 400
    data = response.json()
    assert "detail" in data
    assert "not signed up" in data["detail"]


def test_unregister_already_unregistered_student(client, fresh_activities):
    """Test unregistering the same student twice returns 400 on second attempt."""
    activity_name = "Music Band"
    email = "zara@mergington.edu"
    
    # First unregister - should succeed
    response1 = client.delete(
        f"/activities/{activity_name}/unregister",
        params={"email": email}
    )
    assert response1.status_code == 200
    
    # Second unregister - should fail
    response2 = client.delete(
        f"/activities/{activity_name}/unregister",
        params={"email": email}
    )
    assert response2.status_code == 400
    data = response2.json()
    assert "detail" in data


# ===========================
# Data Integrity & Edge Cases Tests
# ===========================

def test_participant_count_accuracy(client, fresh_activities, sample_emails):
    """Test that participant counts remain accurate after signup/unregister."""
    activity_name = "Debate Team"
    email1 = sample_emails["new_student"]
    email2 = sample_emails["another_student"]
    
    # Get initial state
    initial = client.get("/activities").json()[activity_name]
    initial_count = len(initial["participants"])
    
    # Add two participants
    client.post(f"/activities/{activity_name}/signup", params={"email": email1})
    client.post(f"/activities/{activity_name}/signup", params={"email": email2})
    
    after_signup = client.get("/activities").json()[activity_name]
    assert len(after_signup["participants"]) == initial_count + 2
    
    # Remove one participant
    client.delete(f"/activities/{activity_name}/unregister", params={"email": email1})
    
    after_unregister = client.get("/activities").json()[activity_name]
    assert len(after_unregister["participants"]) == initial_count + 1
    
    # Verify the correct participant is still there
    assert email2 in after_unregister["participants"]
    assert email1 not in after_unregister["participants"]


def test_other_activities_unaffected_by_signup(client, fresh_activities, sample_emails):
    """Test that signup to one activity doesn't affect other activities."""
    email = sample_emails["new_student"]
    
    # Get initial state of all activities
    initial_all = client.get("/activities").json()
    
    # Sign up for one activity
    client.post("/activities/Chess Club/signup", params={"email": email})
    
    # Check other activities are unchanged
    final_all = client.get("/activities").json()
    
    for activity_name in initial_all:
        if activity_name != "Chess Club":
            assert (
                final_all[activity_name]["participants"]
                == initial_all[activity_name]["participants"]
            ), f"{activity_name} should be unaffected by Chess Club signup"


def test_other_activities_unaffected_by_unregister(client, fresh_activities):
    """Test that unregister from one activity doesn't affect other activities."""
    # Get initial state of all activities
    initial_all = client.get("/activities").json()
    
    # Unregister from one activity
    client.delete("/activities/Art Studio/unregister", params={"email": "maya@mergington.edu"})
    
    # Check other activities are unchanged
    final_all = client.get("/activities").json()
    
    for activity_name in initial_all:
        if activity_name != "Art Studio":
            assert (
                final_all[activity_name]["participants"]
                == initial_all[activity_name]["participants"]
            ), f"{activity_name} should be unaffected by Art Studio unregister"


def test_activity_structure_preserved_after_operations(client, fresh_activities, sample_emails):
    """Test that activity structure (description, schedule, max_participants) is preserved."""
    activity_name = "Programming Class"
    email = sample_emails["new_student"]
    
    # Get initial activity data
    initial = client.get("/activities").json()[activity_name]
    initial_description = initial["description"]
    initial_schedule = initial["schedule"]
    initial_max = initial["max_participants"]
    
    # Perform signup
    client.post(f"/activities/{activity_name}/signup", params={"email": email})
    
    # Verify structure is unchanged
    final = client.get("/activities").json()[activity_name]
    assert final["description"] == initial_description
    assert final["schedule"] == initial_schedule
    assert final["max_participants"] == initial_max
