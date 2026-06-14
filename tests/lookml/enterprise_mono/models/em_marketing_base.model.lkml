connection: "acme-analytics"

include: "/views/base/*.view.lkml"
include: "/views/pdts/*.view.lkml"

explore: marketing {
  label: "Marketing & Attribution"
  from: fct_marketing_attribution
  join: fct_cart_abandonment {
    type: left_outer
    sql_on: ${fct_marketing_attribution.metric_date} = ${fct_cart_abandonment.cart_date}
            AND ${fct_marketing_attribution.channel} = ${fct_cart_abandonment.channel} ;;
    relationship: one_to_one
  }
  join: fct_customer_segments {
    type: left_outer
    sql_on: 1=1 ;;
    relationship: many_to_many
  }
}

explore: cart_analysis {
  label: "Cart & Abandonment"
  from: fct_cart_abandonment
  join: fct_marketing_attribution {
    type: left_outer
    sql_on: ${fct_cart_abandonment.cart_date} = ${fct_marketing_attribution.metric_date}
            AND ${fct_cart_abandonment.channel} = ${fct_marketing_attribution.channel} ;;
    relationship: one_to_one
  }
}
