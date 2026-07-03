<template>
  <div class="restocking">
    <div class="page-header">
      <h2>{{ t('restocking.title') }}</h2>
      <p>{{ t('restocking.description') }}</p>
    </div>

    <div v-if="loading" class="loading">{{ t('common.loading') }}</div>
    <div v-else-if="error" class="error">{{ error }}</div>
    <div v-else>
      <div class="card budget-card">
        <div class="card-header">
          <h3 class="card-title">{{ t('restocking.budgetControl') }}</h3>
        </div>
        <div class="budget-control">
          <input
            type="range"
            class="budget-slider"
            v-model.number="budget"
            min="0"
            :max="50000"
            step="500"
          />
          <div class="budget-readout">{{ currencySymbol }}{{ budget.toLocaleString() }}</div>
        </div>
      </div>

      <div class="stats-grid">
        <div class="stat-card info">
          <div class="stat-label">{{ t('restocking.itemsRecommended') }}</div>
          <div class="stat-value">{{ recommendations.length }}</div>
        </div>
        <div class="stat-card warning">
          <div class="stat-label">{{ t('restocking.totalCost') }}</div>
          <div class="stat-value">{{ currencySymbol }}{{ totalRecommendedCost.toLocaleString() }}</div>
        </div>
        <div class="stat-card success">
          <div class="stat-label">{{ t('restocking.remainingBudget') }}</div>
          <div class="stat-value">{{ currencySymbol }}{{ remainingBudget.toLocaleString() }}</div>
        </div>
      </div>

      <div class="card">
        <div class="card-header">
          <h3 class="card-title">{{ t('restocking.itemsRecommended') }} ({{ recommendations.length }})</h3>
        </div>
        <div v-if="recommendations.length === 0" class="empty-state">
          <p>{{ t('restocking.noRecommendations') }}</p>
        </div>
        <div v-else class="table-container">
          <table class="restocking-table">
            <thead>
              <tr>
                <th class="col-sku">{{ t('restocking.table.sku') }}</th>
                <th class="col-name">{{ t('restocking.table.itemName') }}</th>
                <th class="col-trend">{{ t('restocking.table.trend') }}</th>
                <th class="col-gap">{{ t('restocking.table.demandGap') }}</th>
                <th class="col-qty">{{ t('restocking.table.recommendedQty') }}</th>
                <th class="col-cost">{{ t('restocking.table.unitCost') }}</th>
                <th class="col-cost">{{ t('restocking.table.estimatedCost') }}</th>
                <th class="col-lead">{{ t('restocking.table.leadTime') }}</th>
                <th class="col-supplier">{{ t('restocking.table.supplier') }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="item in recommendations" :key="item.item_sku">
                <td class="col-sku">{{ item.item_sku }}</td>
                <td class="col-name">{{ translateProductName(item.item_name) }}</td>
                <td class="col-trend">
                  <span :class="['badge', getTrendClass(item.trend)]">{{ item.trend }}</span>
                </td>
                <td class="col-gap">{{ item.demand_gap }}</td>
                <td class="col-qty">{{ item.recommended_quantity }}</td>
                <td class="col-cost">{{ currencySymbol }}{{ item.unit_cost.toLocaleString() }}</td>
                <td class="col-cost">{{ currencySymbol }}{{ item.estimated_cost.toLocaleString() }}</td>
                <td class="col-lead">{{ item.lead_time_days }}</td>
                <td class="col-supplier">{{ item.supplier_name }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <div v-if="!submittedOrder" class="action-row">
        <button
          class="btn-primary"
          :disabled="submitting || recommendations.length === 0"
          @click="placeOrder"
        >
          {{ t('restocking.placeOrder') }}
        </button>
      </div>
      <div v-else class="success-banner">
        <span>{{ t('restocking.orderSubmitted', { orderNumber: submittedOrder.order_number }) }}</span>
        <router-link to="/orders" class="view-link">{{ t('restocking.viewInOrders') }}</router-link>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, computed, onMounted, watch } from 'vue'
import { api } from '../api'
import { useI18n } from '../composables/useI18n'

export default {
  name: 'Restocking',
  setup() {
    const { t, currentCurrency, translateProductName, translateCustomerName } = useI18n()

    const currencySymbol = computed(() => {
      return currentCurrency.value === 'JPY' ? '¥' : '$'
    })

    const budget = ref(10000)
    const loading = ref(true)
    const error = ref(null)
    const recommendationsData = ref(null)
    const submitting = ref(false)
    const submittedOrder = ref(null)
    const debounceTimer = ref(null)

    const recommendations = computed(() => recommendationsData.value?.recommendations || [])
    const totalRecommendedCost = computed(() => recommendationsData.value?.total_recommended_cost || 0)
    const remainingBudget = computed(() => recommendationsData.value?.remaining_budget || 0)

    const loadRecommendations = async () => {
      try {
        loading.value = true
        error.value = null
        recommendationsData.value = await api.getRestockRecommendations(budget.value)
      } catch (err) {
        error.value = 'Failed to load recommendations: ' + err.message
      } finally {
        loading.value = false
      }
    }

    const placeOrder = async () => {
      if (submitting.value) return
      try {
        submitting.value = true
        const items = recommendations.value.map(r => ({
          item_sku: r.item_sku,
          quantity: r.recommended_quantity
        }))
        submittedOrder.value = await api.createRestockOrder({
          budget: budget.value,
          items
        })
      } catch (err) {
        error.value = 'Failed to place order: ' + err.message
      } finally {
        submitting.value = false
      }
    }

    const getTrendClass = (trend) => {
      const trendMap = {
        'Increasing': 'danger',
        'Rising': 'danger',
        'Decreasing': 'success',
        'Falling': 'success',
        'Stable': 'info'
      }
      return trendMap[trend] || 'info'
    }

    watch(budget, () => {
      if (debounceTimer.value) clearTimeout(debounceTimer.value)
      debounceTimer.value = setTimeout(() => {
        loadRecommendations()
      }, 400)
    })

    onMounted(() => {
      loadRecommendations()
    })

    return {
      t,
      budget,
      loading,
      error,
      recommendations,
      currencySymbol,
      totalRecommendedCost,
      remainingBudget,
      submitting,
      submittedOrder,
      placeOrder,
      getTrendClass,
      translateProductName,
      translateCustomerName
    }
  }
}
</script>

<style scoped>
.budget-card {
  margin-bottom: 1.5rem;
}

.budget-control {
  display: flex;
  align-items: center;
  gap: 1.5rem;
  padding: 0.5rem 0;
}

.budget-slider {
  flex: 1;
  -webkit-appearance: none;
  appearance: none;
  height: 6px;
  border-radius: 3px;
  background: #e2e8f0;
  outline: none;
}

.budget-slider::-webkit-slider-thumb {
  -webkit-appearance: none;
  appearance: none;
  width: 20px;
  height: 20px;
  border-radius: 50%;
  background: #2563eb;
  cursor: pointer;
  border: 2px solid white;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.3);
}

.budget-slider::-moz-range-thumb {
  width: 20px;
  height: 20px;
  border-radius: 50%;
  background: #2563eb;
  cursor: pointer;
  border: 2px solid white;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.3);
}

.budget-slider::-moz-range-track {
  height: 6px;
  border-radius: 3px;
  background: #e2e8f0;
}

.budget-readout {
  font-size: 1.25rem;
  font-weight: 600;
  color: #2563eb;
  min-width: 120px;
  text-align: right;
}

/* Fixed table layout to prevent column shifting */
.restocking-table {
  table-layout: fixed;
  width: 100%;
}

.col-sku {
  width: 110px;
}

.col-name {
  width: 180px;
}

.col-trend {
  width: 100px;
}

.col-gap {
  width: 100px;
}

.col-qty {
  width: 130px;
}

.col-cost {
  width: 120px;
}

.col-lead {
  width: 130px;
}

.col-supplier {
  width: 180px;
}

.empty-state {
  padding: 2rem;
  text-align: center;
  color: #64748b;
}

.action-row {
  display: flex;
  justify-content: flex-end;
  margin-top: 1.5rem;
}

.btn-primary {
  padding: 0.625rem 1.25rem;
  background: #2563eb;
  color: white;
  border: none;
  border-radius: 8px;
  font-weight: 500;
  font-size: 0.9375rem;
  cursor: pointer;
  transition: background 0.2s;
}

.btn-primary:hover:not(:disabled) {
  background: #1d4ed8;
}

.btn-primary:disabled {
  background: #94a3b8;
  cursor: not-allowed;
}

.success-banner {
  margin-top: 1.5rem;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 1rem;
  padding: 1rem;
  background: #16a34a;
  color: white;
  border-radius: 8px;
  font-weight: 500;
}

.view-link {
  color: white;
  text-decoration: underline;
  font-weight: 600;
}

.view-link:hover {
  opacity: 0.85;
}
</style>
