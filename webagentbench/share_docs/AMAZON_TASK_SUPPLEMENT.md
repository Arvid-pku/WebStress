# Amazon Environment Task Supplement

This document is a supplement to `share_docs/TASK_GENERATION_STANDARD.md`. It
defines environment-specific authoring, seeding, and grading rules for the
Amazon e-commerce environment. If this supplement conflicts with the core
standard, fix the supplement.

## Purpose And Scope

- This environment simulates an Amazon-style e-commerce shopping platform with
  product catalogs, cart management, checkout workflows, order lifecycle,
  account settings, and promotional features.
- It is designed to test navigation, product search, cart management, checkout
  flows, order management, account management, and decision-making under
  product catalog complexity.
- In scope: search and browse products, add to cart, update cart quantities,
  checkout, order placement, order cancellation, return requests, wishlist
  management, review creation, address CRUD, payment method CRUD, promo code
  application, gift card redemption, product Q&A, notification management,
  deals discovery.
- Out of scope: real payment processing, real shipping or delivery, marketplace
  seller features, AWS services, Subscribe & Save, digital content (Kindle,
  Prime Video), Amazon Fresh / Whole Foods grocery.

## Environment State Model

The authoritative state model is defined in
`backend/models/amazon.py` (`AmazonState`). The grader inspects durable state
on this model after the agent finishes.

- Primary objects:
  - `Product` with stable ID `product.id` -- fields: name, brand, category,
    subcategory, description, price, list_price, currency, rating,
    review_count, in_stock, stock_quantity, image_url, features, variants
    (list[ProductVariant]), seller, prime_eligible, delivery_estimate
  - `CartItem` with stable ID `cart_item.id` -- fields: product_id,
    product_name, quantity, unit_price, variant_selections, added_at
  - `Order` with stable ID `order.id` -- fields: items (list[OrderItem]),
    shipping_address_id, payment_method_id, subtotal, shipping_cost, tax,
    total, status, placed_at, estimated_delivery, promo_code, discount
  - `OrderItem` (embedded in Order, no own ID) -- fields: product_id,
    product_name, quantity, unit_price, variant_selections
  - `Address` with stable ID `address.id` -- fields: full_name,
    street_address, apt_suite, city, state, zip_code, country, is_default,
    phone
  - `PaymentMethod` with stable ID `pm.id` -- fields: card_type, last_four,
    expiry, holder_name, is_default
  - `Review` with stable ID `review.id` -- fields: product_id, author_name,
    rating, title, body, helpful_count, verified_purchase, created_at
  - `ReturnRequest` with stable ID `return.id` -- fields: order_id,
    order_item_index, product_id, product_name, reason, status, refund_amount,
    created_at, resolution_note
  - `PromoCode` with stable ID `promo.id` -- fields: code, discount_type,
    discount_value, min_order_amount, max_uses, used_count, valid_until,
    applicable_categories, active
  - `ProductQuestion` with stable ID `question.id` -- fields: product_id,
    question, asker_name, answers (list[ProductAnswer]), asked_at, vote_count
  - `GiftCard` with stable ID `gc.id` -- fields: code, balance,
    initial_amount, redeemed, added_at
  - `Notification` with stable ID `notif.id` -- fields: type, title, message,
    read, created_at, related_id
  - `BrowsingHistory` (embedded, no own ID) -- fields: product_id, viewed_at
  - `AmazonSettings` (singleton per session) -- fields: default_address_id,
    default_payment_id, prime_member, one_click_enabled, email_notifications,
    language, currency, two_factor_enabled, order_updates_email,
    deal_alerts_email, gift_card_balance

- Key relationships:
  - `Order.items[].product_id` -> `Product.id`
  - `Order.shipping_address_id` -> `Address.id`
  - `Order.payment_method_id` -> `PaymentMethod.id`
  - `CartItem.product_id` -> `Product.id`
  - `Review.product_id` -> `Product.id`
  - `ReturnRequest.order_id` -> `Order.id`
  - `ReturnRequest.product_id` -> `Product.id`
  - `ProductQuestion.product_id` -> `Product.id`
  - `AmazonSettings.default_address_id` -> `Address.id`
  - `AmazonSettings.default_payment_id` -> `PaymentMethod.id`

- Durable mutations (grader-inspectable):
  - Cart: add, remove, update quantity
  - Orders: place order, cancel order, update order status
  - Addresses: add, update, remove
  - Payment methods: add, remove
  - Reviews: create
  - Returns: request return, update return status
  - Wishlist: add product, remove product
  - Promo codes: apply (increments used_count), clear
  - Gift cards: add, redeem (transfers balance to settings)
  - Notifications: add, mark as read
  - Product questions: ask, answer
  - Settings: default address/payment changes, prime status

- Non-durable or UI-only signals (tracked but not primary grading evidence):
  - `recently_viewed` -- updated on product page visits
  - `browsing_history` -- timestamped product view log
  - `search_history` -- list of past search queries
  - `viewed_order_ids` -- orders the agent has viewed

## Task Definition Shape

- Required top-level fields:
  - `task_id`
  - `env_id: amazon`
  - `title`
  - `instruction_template`
  - `difficulty`
  - `time_limit_seconds`
  - `expected_steps`
  - `primary_primitives`
  - `start_path`
  - `seed`
  - `eval`

- The `primary_primitives` field should list the agent capabilities being
  tested (e.g., `["search", "add_to_cart", "checkout"]`).

- The `start_path` field indicates the initial page the agent sees (e.g.,
  `/`, `/cart`, `/orders`).

- The `seed` field must produce a deterministic initial state for the given
  `(task_id, seed)` pair.

- The `eval` field defines positive and negative evidence checks against the
  final `AmazonState`.

## Instruction Rules For This Environment

- Product selectors must name at least one of: product name, category, price
  range, rating threshold, or brand. Never rely on position in a list or
  visual appearance alone.
- If the task uses "cheapest" or "highest rated", the instruction must specify
  the comparison set (e.g., "among Electronics products under $50") and the
  seeded catalog must guarantee the target product genuinely wins that
  comparison.
- If the task says "default address" or "default payment", the instruction must
  also name it explicitly (e.g., "the Visa ending in 4242" or "the address for
  Jordan Parker in Springfield, IL"). This makes the task auditable without
  inspecting settings state.
- Address fields must all be specified when the task requires adding a new
  address: full_name, street_address, city, state, zip_code.
- Quantity constraints must use exact numbers (e.g., "add 3 units"), never
  vague language like "a few" or "some".
- Variant selections (size, color, etc.) must be spelled out when the task
  requires a specific variant.
- Order status checks must name the expected status value (e.g., "confirmed",
  "cancelled", "delivered").

Environment-specific bad patterns:

- "Buy the best product" -- no selector, "best" is undefined
- "Use the default payment" -- not auditable without naming the method
- "Add suitable items to cart" -- open-ended qualifier
- "Find a good deal" -- no objective threshold
- "Update your address" -- which address? what fields?
- "Leave a review" -- for which product? what rating?

Environment-specific good patterns:

- "Search for 'wireless earbuds' in Electronics, find the product with the
  highest rating (at least 4.5 stars), and purchase it using the address for
  Jordan Parker in Springfield, IL and the Visa ending in 4242."
- "Add 2 units of '{target.product_name}' to your cart."
- "Cancel order '{order.id}' and then request a return for the first item in
  order '{other_order.id}' with reason 'Defective product'."
- "Add a new shipping address: Morgan Lee, 742 Evergreen Terrace, Springfield,
  IL 62704. Set it as the default address."
- "Write a 4-star review titled 'Great value' for the product
  '{target.product_name}'."
- "Apply promo code 'SAVE20' to your cart, then complete checkout using the
  Mastercard ending in 5678 and your default address for Alex Chen in
  Portland, OR."

## State Construction And Decoy Design

- Determinism rules:
  - Seeds are deterministic for a given `(task_id, seed)` pair. Running the
    same seed twice must produce identical initial state.
  - The baseline product catalog adds approximately 300 realistic products
    across 8 categories (Electronics, Books, Home & Kitchen, Clothing, Sports
    & Outdoors, Beauty, Toys & Games, Office Supplies).
  - Each product has internally consistent data: price, rating, review_count,
    brand, features, and delivery estimates.

- Required decoy classes:
  - Similar-named products: e.g., "Wireless Bluetooth Earbuds Pro" vs
    "Wireless Bluetooth Earbuds Pro Max" in the same category
  - Same-category products at similar prices: products within +/-10% of the
    target price to test price-based selectors
  - Products with close ratings: products within 0.1-0.2 rating points of
    the target to test rating-based selectors
  - Same-brand alternatives: other products by the same brand in different
    subcategories
  - Out-of-stock near-matches: products matching selectors but with
    `in_stock=False`

- If the task depends on a comparison rule (cheapest, highest rated, most
  reviewed), the seed must:
  - Ensure the featured/target product genuinely wins the comparison in the
    final seeded catalog
  - Include at least one plausible wrong candidate that a shallow heuristic
    (e.g., picking the first search result, or picking by name similarity)
    would choose
  - Verify the winning margin is non-trivial (not a tie or negligible
    difference)

- Cart and order pre-seeding:
  - Tasks that test checkout should pre-seed at least one address and one
    payment method
  - Tasks that test returns or cancellations should pre-seed at least one
    order with status "confirmed" or "delivered"
  - Tasks that test promo codes should pre-seed the promo code with valid
    dates and sufficient max_uses

## Evaluation Standard For This Environment

- Preferred positive evidence:
  - Order contains specific `product_id` (checked via
    `order.items[].product_id`)
  - `CartItem` matches `product_id` and exact `quantity`
  - Address fields match exactly: `full_name`, `street_address`, `city`,
    `state`, `zip_code`
  - Review `rating` and `title` match expected values
  - Review `product_id` references the correct product
  - Return request references correct `order_id` with correct `reason`
  - Wishlist contains or does not contain specific `product_id`
  - Promo code `used_count` incremented
  - Gift card `redeemed` is `True` and `settings.gift_card_balance` updated
  - Notification `read` field is `True`
  - `AmazonSettings.default_address_id` or `default_payment_id` updated
    correctly

- Preferred negative evidence:
  - Wrong product not purchased (no order or cart item with wrong
    `product_id`)
  - Quantity constraints are exact (`==` not `>=`)
  - Cart is empty after checkout (verified via `len(cart_items) == 0`)
  - Only one order placed when instruction implies a single order
    (`len(orders)` checked)
  - Cancelled order has `status == "cancelled"`, not just removed
  - No unintended address or payment method mutations
  - Decoy products remain unpurchased

- Use transient DOM evidence only when:
  - The task explicitly tests whether the agent can read and report UI content
    (e.g., "What is the price of..."), not when it tests a state mutation

## Format-Tolerant Grading Rules

- Accept any review body text as long as it is non-empty, unless the
  instruction provides exact body text.
- Address matching must be exact on all specified fields (`full_name`,
  `street_address`, `city`, `state`, `zip_code`). Do not normalize or
  fuzzy-match addresses.
- Product identification is always by `product_id`, never by name substring
  matching. Name substrings are fragile when decoys share similar names.
- Accept semantic equivalence across:
  - Ordering differences in cart items (items may appear in any order)
  - Capitalization in promo codes (`SAVE20` vs `save20` -- the state model
    matches by exact code, so the instruction must use the exact code)
  - Timestamp precision (do not grade on exact `placed_at` or `created_at`
    values)
- Require exact text only when:
  - The instruction provides exact text for a review title
  - The instruction provides an exact promo code string
  - The literal text is itself the skill being tested

## Required Negative-Check Categories

- Wrong-product mutation: order or cart contains a decoy product instead of
  the target
- Extra-quantity mutation: cart quantity exceeds the instructed amount
- Wrong-address mutation: order shipped to an address not specified in the
  instruction
- Wrong-payment mutation: order charged to a payment method not specified in
  the instruction
- Unintended order placement: extra orders created beyond what the instruction
  requires
- Unintended cancellation: orders cancelled that should not have been
- Protected-state mutation: addresses, payment methods, or settings changed
  when the task did not require it
- Partial completion masked as completion: e.g., items added to cart but
  checkout not completed when the instruction says "purchase"

## Variants

- Variants may stress:
  - `patience` -- API delays on search results or checkout confirmation
  - `verification` -- silent failures (e.g., add-to-cart appears to succeed
    but cart remains empty)
  - `backtracking` -- 503 errors on first attempt requiring retry
  - `grounding` -- similar products injected into search results to test
    product discrimination
  - `state_tracking` -- product order shuffled in search results across
    page loads
  - `exploration` -- failed operations (out-of-stock products, expired promo
    codes) requiring the agent to find alternatives
  - `planning` -- empty search results for initial queries requiring
    reformulation

- Variants must not change:
  - Which product is the correct answer (the target `product_id` is invariant)
  - The task objective (what the agent must accomplish)
  - The grading contract (what evidence is checked and how)
  - The seeded catalog composition that makes the target product win any
    specified comparison

- Variant fake responses or degraded client behavior must preserve:
  - The final state model accuracy (all mutations must still be durable)
  - The ability to eventually complete the task (variants add difficulty, not
    impossibility)

## Validation Suite

Run these commands before treating any Amazon task as benchmark-ready:

```bash
python -m pytest -q tests/test_task_linter.py
python -m pytest -q tests/test_scoring_audit.py
python -m pytest -q tests/test_amazon_seed_integrity.py
python -m pytest -q tests/test_amazon_seed_stability.py
python -m pytest -q tests/test_benchmark_integrity.py
```

Environment-specific audits:

- `tests/test_amazon_seed_integrity.py`: Verifies that session creation
  succeeds for every Amazon task (no unresolved `{output.}` templates in
  instructions), that all evaluation expressions run without errors against
  the seeded state, that order detail views are tracked in `viewed_order_ids`,
  and that the promo-code apply/clear/checkout flow is consistent.

- `tests/test_amazon_seed_stability.py`: Verifies deterministic seed
  stability (same task_id + seed always produces identical state), that
  comparison task targets (highest-rated, cheapest, best deal) genuinely
  win their comparisons across seeds 0-19, that the price comparison task
  has at least 3 products in the $50-$100 range, and that no Amazon task
  trivially passes with zero agent actions.

## Environment-Specific Anti-Patterns

- Verifying cart or order contents by product name substring instead of
  `product_id`. Name substrings break when decoy products share similar names.
- Using `>=` for quantity checks when the instruction specifies an exact number.
  "Add 2 units" means exactly 2, not at least 2.
- Hardcoding target values (prices, ratings, product names) in evaluation
  instead of deriving them from builder outputs. Hardcoded values break when
  seeds change.
- Seeding a "highest rated" product without verifying it actually has the
  highest rating in the final catalog after all decoys are added.
- Using "default" as a selector in instructions without naming the specific
  address or payment method. The grader cannot audit intent from "default"
  alone.
- Grading checkout success by checking only that an order exists, without
  verifying the order contains the correct `product_id`, correct quantity,
  correct `shipping_address_id`, and correct `payment_method_id`.
- Scoring on visible search result text alone when durable cart/order state
  exists and should be the primary evidence.
- Requiring exact prose in review bodies when semantic checks would suffice
  (unless the instruction gave exact text).
- Using unrealistic decoys that no competent agent would confuse (e.g., a
  laptop as a decoy for earbuds). Decoys must be plausible near-misses.

## Environment Readiness Checklist

Before adding or revising tasks in this environment, verify:

- [ ] This supplement still agrees with `TASK_GENERATION_STANDARD.md`
- [ ] The environment exposes durable state for authoritative grading (all
  mutations reflected in `AmazonState`)
- [ ] Product selectors and tie-break rules are documented for common ambiguity
  classes (price ties, rating ties, name similarity)
- [ ] Decoys reflect realistic failure modes (similar names, close prices,
  close ratings, same brand)
- [ ] Free-form outputs (review bodies, question answers) are graded
  semantically when appropriate
- [ ] Variants preserve the same semantic task and grading contract
- [ ] The validation suite covers seed determinism, comparison correctness,
  and decoy presence
- [ ] Address and payment method references in instructions are explicit and
  auditable
- [ ] Quantity constraints use exact numbers throughout
