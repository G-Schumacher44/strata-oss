# Two models declare an explore with the same name over different views: Looker keys an
# explore by model, so `retail.orders` and `wholesale.orders` are two explores (strata N9).
connection: "twin"

include: "/views/*.view.lkml"

explore: orders {
  from: retail_orders
}
