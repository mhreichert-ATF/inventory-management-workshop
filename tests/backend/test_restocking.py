"""
Tests for Restocking API endpoints.
"""
import pytest


class TestRestockingRecommendations:
    """Test suite for restocking recommendations endpoint."""

    def test_get_recommendations_with_budget(self, client):
        """Test getting restocking recommendations with a budget."""
        response = client.get("/api/restocking/recommendations?budget=5000")
        assert response.status_code == 200

        data = response.json()
        assert "budget" in data
        assert "total_recommended_cost" in data
        assert "remaining_budget" in data
        assert "recommendations" in data
        assert isinstance(data["recommendations"], list)
        assert data["budget"] == 5000
        assert data["total_recommended_cost"] <= 5000
        assert data["remaining_budget"] >= 0

    def test_recommendations_sorted_by_priority(self, client):
        """Test that recommendations are sorted by descending priority/demand gap."""
        response = client.get("/api/restocking/recommendations?budget=100000")
        assert response.status_code == 200

        data = response.json()
        recommendations = data["recommendations"]

        if len(recommendations) > 1:
            # Check that demand gaps are in descending order
            demand_gaps = [r["demand_gap"] for r in recommendations]
            assert demand_gaps == sorted(demand_gaps, reverse=True)

    def test_recommendations_with_zero_budget(self, client):
        """Test that zero budget returns empty recommendations."""
        response = client.get("/api/restocking/recommendations?budget=0")
        assert response.status_code == 200

        data = response.json()
        assert data["total_recommended_cost"] == 0.0
        assert data["remaining_budget"] == 0.0
        assert len(data["recommendations"]) == 0

    def test_recommendations_include_required_fields(self, client):
        """Test that recommendations include all required fields."""
        response = client.get("/api/restocking/recommendations?budget=10000")
        assert response.status_code == 200

        data = response.json()
        if data["recommendations"]:
            rec = data["recommendations"][0]
            required_fields = [
                "item_sku", "item_name", "current_demand", "forecasted_demand",
                "demand_gap", "trend", "unit_cost", "recommended_quantity",
                "estimated_cost", "lead_time_days", "supplier_name",
                "has_inventory_match"
            ]
            for field in required_fields:
                assert field in rec

    def test_lead_times_are_deterministic(self, client):
        """Test that lead times are consistent across calls for same SKU."""
        # Get recommendations twice
        response1 = client.get("/api/restocking/recommendations?budget=100000")
        response2 = client.get("/api/restocking/recommendations?budget=100000")

        data1 = response1.json()
        data2 = response2.json()

        # Build maps of SKU to lead time
        lead_times_1 = {r["item_sku"]: r["lead_time_days"] for r in data1["recommendations"]}
        lead_times_2 = {r["item_sku"]: r["lead_time_days"] for r in data2["recommendations"]}

        # Check that all SKUs match in lead time
        assert lead_times_1 == lead_times_2


class TestRestockingOrders:
    """Test suite for restocking order creation and retrieval."""

    def test_create_restock_order(self, client):
        """Test creating a restocking order."""
        order_data = {
            "budget": 5000,
            "items": [
                {"item_sku": "WDG-001", "quantity": 150},
                {"item_sku": "BRG-102", "quantity": 50}
            ]
        }
        response = client.post("/api/restocking/orders", json=order_data)
        assert response.status_code == 201

        order = response.json()
        assert order["id"] == "1"
        assert order["order_number"].startswith("RO-")
        assert len(order["items"]) == 2
        assert order["status"] == "Processing"
        assert order["budget_used"] == 5000
        assert order["total_value"] > 0
        assert order["max_lead_time_days"] > 0

    def test_create_order_with_nonexistent_sku(self, client):
        """Test that creating order with unknown SKU returns 404."""
        order_data = {
            "budget": 5000,
            "items": [
                {"item_sku": "UNKNOWN-SKU-999", "quantity": 100}
            ]
        }
        response = client.post("/api/restocking/orders", json=order_data)
        assert response.status_code == 404

    def test_order_line_items_structure(self, client):
        """Test that order line items have correct structure."""
        order_data = {
            "budget": 5000,
            "items": [{"item_sku": "WDG-001", "quantity": 150}]
        }
        response = client.post("/api/restocking/orders", json=order_data)
        assert response.status_code == 201

        order = response.json()
        item = order["items"][0]

        required_fields = [
            "item_sku", "item_name", "quantity", "unit_cost",
            "line_total", "lead_time_days", "supplier_name"
        ]
        for field in required_fields:
            assert field in item

    def test_order_total_value_calculation(self, client):
        """Test that total value is correctly calculated."""
        order_data = {
            "budget": 5000,
            "items": [{"item_sku": "WDG-001", "quantity": 150}]
        }
        response = client.post("/api/restocking/orders", json=order_data)
        assert response.status_code == 201

        order = response.json()

        # Calculate from line items
        calculated_total = sum(item["line_total"] for item in order["items"])
        assert abs(order["total_value"] - calculated_total) < 0.01

    def test_get_restocking_orders(self, client):
        """Test retrieving all restocking orders."""
        # Create an order first
        order_data = {
            "budget": 5000,
            "items": [{"item_sku": "WDG-001", "quantity": 150}]
        }
        create_response = client.post("/api/restocking/orders", json=order_data)
        assert create_response.status_code == 201

        # Get all orders
        response = client.get("/api/restocking/orders")
        assert response.status_code == 200

        orders = response.json()
        assert isinstance(orders, list)
        assert len(orders) >= 1

        # Check that our created order is in the list
        created_order = create_response.json()
        found = any(o["id"] == created_order["id"] for o in orders)
        assert found

    def test_max_lead_time_is_correct(self, client):
        """Test that max_lead_time_days is the maximum of all line items."""
        order_data = {
            "budget": 15000,
            "items": [
                {"item_sku": "WDG-001", "quantity": 10},
                {"item_sku": "BRG-102", "quantity": 10},
                {"item_sku": "PSU-501", "quantity": 10}
            ]
        }
        response = client.post("/api/restocking/orders", json=order_data)
        assert response.status_code == 201

        order = response.json()

        # Max lead time should be the max of all line items
        line_lead_times = [item["lead_time_days"] for item in order["items"]]
        expected_max = max(line_lead_times)
        assert order["max_lead_time_days"] == expected_max

    def test_order_number_format(self, client):
        """Test that order numbers follow RO-NNNN format."""
        order_data = {
            "budget": 5000,
            "items": [{"item_sku": "WDG-001", "quantity": 100}]
        }
        response = client.post("/api/restocking/orders", json=order_data)
        assert response.status_code == 201

        order = response.json()
        # Should be RO-0001, RO-0002, etc.
        assert order["order_number"].startswith("RO-")
        assert len(order["order_number"]) == 7  # RO-NNNN (7 chars)

    def test_order_has_processing_status(self, client):
        """Test that new orders have 'Processing' status."""
        order_data = {
            "budget": 5000,
            "items": [{"item_sku": "WDG-001", "quantity": 100}]
        }
        response = client.post("/api/restocking/orders", json=order_data)
        assert response.status_code == 201

        order = response.json()
        assert order["status"] == "Processing"

    def test_order_has_order_date(self, client):
        """Test that new orders have an order_date in ISO format."""
        order_data = {
            "budget": 5000,
            "items": [{"item_sku": "WDG-001", "quantity": 100}]
        }
        response = client.post("/api/restocking/orders", json=order_data)
        assert response.status_code == 201

        order = response.json()
        assert "order_date" in order
        assert "T" in order["order_date"]  # ISO format includes T
