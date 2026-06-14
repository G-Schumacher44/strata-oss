# LEGACY — written before silver v2 migration. References unit_cost_usd which was
# dropped when cost accounting moved to the gold_marts layer in Q1 2025.
# Schema drift: unit_cost_usd no longer exists on int_attributed_purchases.
# DO NOT USE — migrate to int_attributed_purchases + fct_product_profitability join.
view: legacy_order_detail {
  sql_table_name: `acme-analytics.silver.int_attributed_purchases` ;;

  dimension: order_id {
    type: string
    sql: ${TABLE}.order_id ;;
    primary_key: yes
  }

  dimension: order_dt {
    type: date
    sql: ${TABLE}.order_dt ;;
  }

  dimension: order_channel {
    type: string
    sql: ${TABLE}.order_channel ;;
  }

  dimension: customer_tier {
    type: string
    sql: ${TABLE}.customer_tier ;;
  }

  # DRIFT: unit_cost_usd dropped in silver v2
  dimension: unit_cost {
    type: number
    sql: ${TABLE}.unit_cost_usd ;;
    value_format_name: usd
  }

  # DRIFT: liquid param + dropped column — cursed margin calc
  dimension: regional_gross_margin {
    type: number
    sql:
      {% if _user_attributes['region'] == 'US' %}
        ${TABLE}.gross_total - (${TABLE}.unit_cost_usd * 1.0)
      {% elsif _user_attributes['region'] == 'EU' %}
        (${TABLE}.gross_total - ${TABLE}.unit_cost_usd) * 0.92
      {% elsif _user_attributes['region'] == 'APAC' %}
        (${TABLE}.gross_total - ${TABLE}.unit_cost_usd) * 0.85
      {% else %}
        ${TABLE}.gross_total - ${TABLE}.unit_cost_usd
      {% endif %}
    ;;
    value_format_name: usd
  }

  measure: order_count {
    type: count_distinct
    sql: ${TABLE}.order_id ;;
  }

  measure: gross_total {
    type: sum
    sql: ${TABLE}.gross_total ;;
    value_format_name: usd
  }

  measure: net_total {
    type: sum
    sql: ${TABLE}.net_total ;;
    value_format_name: usd
  }

  measure: total_unit_cost {
    type: sum
    sql: ${TABLE}.unit_cost_usd ;;
    value_format_name: usd
  }
}
