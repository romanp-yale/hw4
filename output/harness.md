# Campus Customs harness

## Data source and scope

This document begins the operating guide for the Campus Customs shop and chatbot. The source is the local SQLite file `data/campus_customs.db`, inspected on September 30, 2026. The data pack stays outside Git. The supplied snapshot contained 102 catalogue products, 612 product-size inventory records, 3 users, and 22 chat messages. Problem 4 verification created one additional local test account. These counts do not represent live shop availability.

The numbered sections below retain the implementation history. Statements such as “three tools” describe the earlier Problem 5–6 version; the current, complete five-tool configuration and operating limits are listed in the Problem 12 reference at the end of this document.

The shop should read price from `catalogue` and size-specific stock from `inventory` when answering shoppers. Product descriptions or search tags are useful for finding items, but they do not establish current price or availability.

## `catalogue` — products the shop can show

One row represents one product. `product_id` is the primary key. Every listed field is required in the database.

| Field | Why it matters to the shop or chatbot |
| --- | --- |
| `product_id` (text) | Stable product identifier. It connects a product to its size-level inventory and lets the site refer to the same item consistently. |
| `name` (text) | Shopper-facing product title for cards, search results, and chat recommendations. |
| `garment_type` (text) | Product category, such as a hoodie or T-shirt. It helps narrow a request to the right kind of item. |
| `description` (text) | Product details the chatbot can summarize when explaining why an item matches a shopper's request. |
| `colors` (text containing a JSON list) | Available color labels for product display and color-based search. A color appearing here does not prove that every size is in stock. |
| `search_tags` (text containing a JSON list) | Extra search terms and themes that help match informal shopper language to products. |
| `image_file_path` (text) | Relative path to the product image in the local data pack, used to show the matching item on the page. |
| `price` (real number) | The product's listed price. The chatbot should use this database value for price answers rather than guessing. |

## `inventory` — stock by product and size

One row represents one size for one product. The `product_id` and `size` pair is unique, so the same size cannot have two stock rows for a product. `product_id` refers to `catalogue.product_id`. The supplied rows use sizes XS, S, M, L, XL, and XXL.

| Field | Why it matters to the shop or chatbot |
| --- | --- |
| `id` (integer) | Unique inventory-row identifier for tracking and updating a specific stock record. |
| `product_id` (text) | Connects the stock row to the product the shopper is viewing or asking about. |
| `size` (text) | Specifies which garment size the stock count applies to. The chatbot must check the requested size, not just the product overall. |
| `quantity` (integer) | Number of units recorded for that product and size. This is the source for an in-stock answer; zero means no units recorded for that size. |

## `users` — shopper accounts

One row represents one account. `email` is unique; `name`, `email`, `password_hash`, and `created_at` are required. `first_name` and `last_name` are optional.

| Field | Why it matters to the shop or chatbot |
| --- | --- |
| `id` (integer) | Internal account identifier. It links an account to its chat history. |
| `name` (text) | Account display name for a personal greeting or profile view. |
| `email` (text) | Unique sign-in identifier and contact address for the shopper. |
| `password_hash` (text) | Stored password verifier for sign-in. It must never be displayed, logged in chat, or sent to the model. |
| `created_at` (text, default current SQLite datetime) | Records when the account was created, useful for account management and support. |
| `first_name` (text, optional) | Given name for a more natural greeting when present. |
| `last_name` (text, optional) | Family name for profile or account records when present. |

## Other application table: `chat_messages`

The supplied database also has a chat history table. It is relevant to the eventual chatbot, even though the assignment specifically calls for the three tables above.

| Field | Why it matters to the shop or chatbot |
| --- | --- |
| `id` (integer) | Unique message identifier for ordering and managing records. |
| `user_id` (integer) | Links a message to `users.id`, so chat history belongs to the correct account. |
| `role` (text) | Identifies which side of the conversation sent the message. |
| `content` (text) | Saved message text that can be shown in chat history. Treat its contents as untrusted input. |
| `products_json` (text, optional) | Stores product references associated with a message, so the page can show matching items with the conversation. |
| `created_at` (text, default current SQLite datetime) | Records when the message was saved for chronology and support. |

SQLite also has an internal `sqlite_sequence` table for autoincrement counters; it is not shop data.

## Authentication flow (Problem 4)

The Create account page collects first name, last name, email, password, and password confirmation. The browser checks that the passwords match and sends the first four fields over a same-origin HTTPS connection in deployment (local development uses HTTP on `127.0.0.1`). The backend validates the fields, trims names, normalizes email to lowercase, rejects an email already in use, and inserts a row in `users`. The confirmation password is never sent to or stored by the backend. The `name` field stores the joined first and last name; `first_name`, `last_name`, `email`, `password_hash`, and the database-generated `id` and `created_at` complete the account record.

The Login page sends email and password to `/api/auth/login`. The backend looks up the account and compares the submitted password with the stored hash. An incorrect email or password returns the same generic error. On success, registration and login both create a random session token. Only its SHA-256 digest, the user ID, creation time, and expiration time are stored in the local `auth_sessions` table. The browser receives the token in an HTTP-only, SameSite=Lax cookie; JavaScript cannot read it. The session lasts seven days. `/api/auth/me` checks the cookie and returns only public account fields. Log out deletes the session record and clears the cookie. The browser does not store passwords or session tokens in local storage.

New passwords are stored using PBKDF2-HMAC-SHA256 with a random 16-byte salt and 600,000 iterations; the stored value records the algorithm, work factor, salt, and derived hash. Passwords are never stored in plaintext or returned by the API. The starter database uses an older three-part PBKDF2-SHA256 format with 120,000 iterations. Login verifies that format and upgrades a successful login to the stronger format. Hash comparison uses constant-time `hmac.compare_digest`. The local development cookie is not marked Secure so it works over localhost HTTP; set `COOKIE_SECURE=1` when serving the app over HTTPS. The database and its session records remain inside the Git-ignored `data/` folder.

The 600,000-iteration PBKDF2-HMAC-SHA256 setting follows the [OWASP Password Storage Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html). The salt is generated with Python's `secrets` module for each new hash.

Verification on September 30, 2026: a new account was registered, received a session, logged out, logged back in with its password, and received a new valid session. An incorrect password was rejected. The supplied `test@campuscustoms.yale.edu` account logged in with the provided password; its older hash was upgraded after that successful login. The browser login form also reached the signed-in account page and retained the session after a refresh. The local verification account remains in the ignored database as test data.

This is a local assignment authentication flow. A public deployment would also need HTTPS, login rate limiting, account recovery, and operational session management.

## Chat agent and website connection (Problem 5)

The React chat widget sends `POST /api/chat` through Vite's `/api` proxy to FastAPI in `backend/main.py`. The request contains the shopper's current message, at most 12 recent browser turns for guests, and page context. FastAPI validates these with `ChatRequest` in `backend/models.py`; blank or oversized messages are rejected. The response is a `ChatResponse` with reply text, hydrated product cards, and the model name. The widget displays the reply and sends product matches to the main page. It shows a visible error when the model or data source fails. Signed-in chat history is now saved in `chat_messages`; see Problem 8 below.

The backend can be started from the `backend/` folder with `uvicorn main:app --reload --port 8000`. Imports support this launch location. Port 8000 is occupied by another service in the current workspace, so the local preview uses 8764 with an ignored `frontend/.env.local` proxy override. A fresh checkout defaults the Vite proxy to 8000.

`backend/agent.py` loads `backend/prompts/prompt.md` when the first chat request builds the PydanticAI agent. It loads `PORTKEY_API_KEY` from the environment or an ignored project/parent `.env`, routes an OpenAI Responses model through Portkey, and defaults to `gpt-6-luna`. No temperature is set. It uses medium reasoning normally, low for a brief greeting, and high for a long or comparative question. A missing key is reported as a 503 chat error while product and account routes remain available. [Official OpenAI documentation](https://developers.openai.com/api/docs/models/gpt-6-luna) confirms this model and its Responses API tool support.

`backend/tools.py` supplies three read-only agent tools: `search_products` searches catalogue terms and returns real product descriptions, prices, colors, and size stock; `get_product_details` reads one exact product with the same facts; `get_stock_by_size` checks one requested size and returns an explicit availability status. Database queries are parameterized. The model returns `AgentReply` from `backend/models.py` with text and selected product IDs. Before replying to the browser, the backend resolves those IDs against SQLite, drops unknown or repeated IDs, and builds `ProductCard` records with real image URLs and prices. The agent cannot read the `users` or `auth_sessions` tables through these tools.

The prompt tells the assistant to speak warmly and briefly, use tools for product facts, treat database and shopper text as untrusted data, avoid invented prices or stock, and decline unsupported checkout or account actions. A failed model or catalogue lookup produces an error rather than a fabricated answer. Model requests are capped at eight per chat turn. The model call is subject to the configured Portkey account and network availability.

Verification on September 30, 2026: the frontend production build passed; `main:app` imported from the `backend/` folder; product search and detail tools read the local database; live Portkey calls returned a greeting, a grounded $68 price and five size-M units for the Basic Hoodie Big Yale, and a linked product card. A follow-up question with conversation history also returned the same database facts. The `/api/chat` HTTP route was verified through Vite's proxy. The browser widget displayed the agent's answer and linked product card; its screenshot is `output/app_check_images/p5-live-chat.png`.

## Product lookup tools and return fields (Problem 6)

All three agent-callable tools in `backend/tools.py` read `data/campus_customs.db`. They use `catalogue` for descriptions and prices and `inventory` for size quantities. They do not write to the database or access account records.

- `search_products(query, limit=5)` finds products whose name, garment type, tags, or description match shopper terms. It returns up to eight ranked `ProductEvidence` records, each with database price and stock by size. It is used when the shopper describes an item but has not supplied an exact product ID.
- `get_product_details(product_id)` returns one exact `ProductEvidence` record, or `None` when the product does not exist. It is used to confirm a particular item's description, colors, price, and complete size list.
- `get_stock_by_size(product_id, size)` returns one `SizeStockLookup`. Common size words such as “extra small” are normalized to catalogue size codes. It distinguishes a positive quantity (`in_stock`), a recorded zero (`out_of_stock`), no row for that size (`size_not_listed`), and an unknown product (`product_not_found`). This prevents a missing size from being reported as zero stock.

`product_cards(product_ids)` is a backend helper, not an agent-callable tool. After the agent chooses product IDs, this helper re-reads real names, descriptions, prices, and image URLs from `catalogue` for the website cards. Unknown and duplicate IDs are discarded.

The lookup models in `backend/models.py` use these fields:

- `ProductEvidence.product_id` ties a result to inventory and a clickable card; `name` gives the shopper-facing title; `garment_type` and `colors` support meaningful matching; `description` supplies factual product details; `price` supplies the listed database price; and `inventory` carries the size records needed for stock answers.
- Each `StockItem` has `size` so quantities cannot be confused across sizes, `quantity` for the exact recorded unit count, and `availability` to make a zero count explicitly mean out of stock.
- `SizeStockLookup.product_id` and `product_name` identify what was checked; `requested_size` preserves the shopper's wording; `size` gives the normalized database size; `quantity` is the exact count or `null` when no count exists; `status` states which of the four cases occurred; and `price` lets the assistant answer a combined price-and-stock question from the same verified product.
- `ProductCard.product_id` creates the detail-page link; `name`, `garment_type`, and `description` help the shopper recognize the item; `price` comes from the catalogue rather than the model's text; and `image_url` points to the backend image route.

The prompt requires the agent to call `get_stock_by_size` for any specific-size question and to say “out of stock” clearly when the returned status is `out_of_stock`. Descriptions, prices, and quantities must come from tool results, not model memory or shopper claims. In the local database, 145 size rows have a quantity of zero. Verification used the Baseball Left Chest Crewneck: `get_stock_by_size` returned XS quantity 0 and `out_of_stock`, M quantity 5 and `in_stock`, while a live model answer stated “XS is out of stock” and cited the database price of $58. The same question sent through the website's `/api/chat` proxy returned “XS is currently out of stock,” one product card priced at $58, and the product route still returned all 102 items.

## Harness sections to expand later

This heading was created while the harness was still in progress. The Problem 8–12 sections below complete the customer context, usability, result contract, model, safety, audit, and operating details listed here. The earlier Problem 5–6 three-tool and eight-result descriptions remain as the implementation history; the current five-tool set and caps are specified in the Problem 12 reference.

## Customer memory and page context (Problem 8)

`GET /api/chat/history` reads up to 50 recent `chat_messages` rows for the authenticated user, ordered oldest first for the widget. Each successful signed-in `POST /api/chat` writes two rows in one SQLite transaction: the customer's message and the assistant reply. The assistant row also stores returned product IDs in `products_json`. Rows use the existing `user_id` foreign key, `role`, `content`, and database timestamp. The HTTP-only session cookie is checked server-side; a request cannot choose a user ID. The server ignores browser-supplied history for signed-in customers and loads the latest 12 turns from their database rows for agent context. Failed agent calls are not saved. Guests can chat with recent browser-memory turns, but have no saved history. The frontend reloads signed-in history after a refresh or login and clears visible messages on logout or user change.

The authenticated customer context is passed to PydanticAI through a `ChatDeps` object. The agent's per-run instructions see the customer's `name` and `email`; the dependency also holds the user ID internally for server operations, but the model prompt contains only name and email. Password hashes, session tokens, and other users' records are never included. This identity is sourced from the server-verified session, never from a client-provided field. The prompt limits its use to appropriate personalization and account identity. Because the model is served through Portkey, these two identity fields are sent to that external model provider during signed-in chat.

The browser sends `PageContext.kind` for the current route and `product_id` on a product detail route. FastAPI checks that ID against `catalogue` through `get_product_details` before constructing agent dependencies. For a valid product page, runtime instructions give the model the verified product ID and name and tell it to resolve “this” or “it” to that item, then call product tools for colors, price, or stock. An invalid ID establishes no current product; the model is told to ask for clarification if needed. The page context is sent on every chat turn, so navigation changes the referent immediately.

Verification: the frontend production build and backend import passed. An offline HTTP check verified guest chat without persistence, a signed-in request that ignored forged browser history, two saved rows in SQLite, and history reload for that user. After the user approved the live test, the seeded account logged in, asked “Do you have this in pink?” on the Basic Hoodie Big Yale page, and received a grounded answer that its listed colors are navy blue and white. The saved history increased by two turns with user and assistant roles.

## Usability additions (Problem 9)

The Products API now includes `available_sizes` and `total_stock` derived from positive inventory quantities. The Products page can sort by name or price and filter to products with stock in a selected size. Product detail pages show up to four other catalogue products with the same garment type. Full rationale and browser verification are in `output/usability.md`.

Two more read-only agent tools extend `backend/tools.py`: `find_products_by_color(color, query, limit)` checks the actual catalogue color list before recommending an item; `find_in_stock_products(query, size, limit)` joins inventory and only returns products with a positive quantity in the normalized size. Both return `ProductEvidence`, so product IDs, prices, colors, and stock remain grounded in SQLite. The prompt directs the agent to use these tools for color and size-filtered recommendations and to avoid an unfiltered `search_query` for those answers. A live guest test reported no pink hoodies and gave positive medium-size quantities for hoodie recommendations.

## Chat-driven catalogue results (Problem 7)

For a category request, the PydanticAI agent calls `search_products` to ground its answer and returns a structured `AgentReply` with `reply` and a focused `search_query` such as `hoodie`. FastAPI searches SQLite again using that query, resolves matching product IDs into `ProductCard` records, and returns `ChatResponse` containing `reply`, `search_query`, `products`, and `model`. The server caps page results at 30. The model does not write prices, descriptions, or image URLs into the API cards; those fields are read from `catalogue`. Singular and common plural category terms are normalized by the search tool.

The React widget posts the conversation to `/api/chat` and passes returned `products` to the main page. A results section displays them with the same `ProductCard` component and CSS used on the normal Products page. Each card links to `/products/:productId`; that route loads the full product and size-level stock from FastAPI. Navigating to a product clears the results section so the detail view is visible. If the API fails, the widget displays the error and does not invent matches.

For a specific item recommendation, `search_query` is null and the server instead resolves up to four agent-selected `product_ids` into the same card type. This preserves the existing product-answer flow while letting category searches show a fuller catalogue set.

- Models and provider configuration
- Additional safety and privacy controls
- System specifications and operating checks

All three items above are covered in the current system reference below.

## Current system reference and audit trail (Problem 12)

### Validated models in `backend/models.py`

- `ChatTurn`: `role` is limited to `user` or `assistant` to keep conversation order clear; `content` holds one nonempty turn, capped at 3,000 characters so saved replies fit while context stays bounded.
- `PageContext`: `kind` names the current route (`home`, `products`, `product`, `about`, `account`, or `other`); optional `product_id` carries at most 120 characters. The backend verifies that ID against the catalogue before using it as the referent for “this.”
- `ChatRequest`: `message` is the shopper's current 1–2,000-character question; `history` carries at most 12 guest turns; optional `page` supplies route context. For signed-in users the server discards supplied history and reads their own saved turns.
- `StockItem`: `size` labels a single inventory row, nonnegative `quantity` is its unit count, and `availability` explicitly marks positive stock or recorded zero. The fields keep one size's stock from being confused with another's.
- `SizeStockLookup`: `product_id` and optional `product_name` identify the item; `requested_size` preserves the shopper's phrase, while `size` holds the normalized code. Nullable nonnegative `quantity` distinguishes no row from zero. `status` distinguishes `in_stock`, `out_of_stock`, `size_not_listed`, and `product_not_found`; nullable `price` lets a combined price-and-stock answer use the same verified product.
- `ProductEvidence`: `product_id`, `name`, `garment_type`, `description`, `colors`, and nonnegative `price` are the catalogue facts given to the agent. `inventory` is a list of `StockItem` records, allowing size-specific answers and recommendations with real stock evidence.
- `ProductCard`: `product_id` supplies the detail-route link; `name`, `garment_type`, and `description` explain the match; nonnegative `price` and `image_url` are loaded by the backend from the catalogue for rendering, not written by the model.
- `AgentReply`: `reply` is the model's 1–3,000-character shopper-facing text; `product_ids` holds at most four tool-grounded IDs for specific recommendations; optional `search_query` (maximum 80 characters) asks the backend to build a fuller category result set without trusting model-written product cards.
- `ChatResponse`: `reply` is the delivered answer; `products` holds structured `ProductCard` matches; optional `search_query` labels a category search; `model` identifies the configured model for support and debugging.

### Tools, capabilities, and bounds

The PydanticAI agent registers five read-only tools in `backend/agent.py`; all read the ignored local SQLite database through `backend/tools.py` and use parameterized queries. `search_products(query, limit=5)` ranks catalogue names, garment types, tags, and descriptions, normalizes common plural category words, and returns up to 30 `ProductEvidence` results. `get_product_details(product_id)` returns one exact product with colors, description, price, and all size rows, or `None`. `get_stock_by_size(product_id, size)` checks one normalized size and reports the four explicit status cases. `find_products_by_color(color, query="", limit=5)` checks actual catalogue color labels before ranking an optional category, capped at eight results. `find_in_stock_products(query, size, limit=5)` joins inventory and returns only products with positive quantity in the normalized size, also capped at eight. Tool return models and field purposes are listed above.

`product_cards` is a server helper, not a model-callable tool. It re-reads selected IDs from SQLite, drops unknown and duplicate IDs, and caps specific recommendations at four or category results at 30. The site displays these results with the same card component as the Products page. The agent cannot call account-writing routes, read password hashes, change stock, place orders, or see payment information. Its capabilities are catalogue search, product details, size checks, color checks, size-filtered recommendations, and short conversational guidance. Its dependencies add verified customer name/email and the current page/product without exposing database credentials or session tokens.

The agent is built once per backend process from `backend/prompts/prompt.md`. It defaults to `gpt-6-luna` through Portkey's OpenAI Responses-compatible endpoint, using `PORTKEY_API_KEY`; `PORTKEY_MODEL` and `PORTKEY_BASE_URL` are optional overrides. No temperature is set. Reasoning effort is low for simple greetings, high for long or comparative questions, and medium otherwise. One turn permits at most eight model requests and 12 tool calls. The request accepts at most 12 prior turns. Category cards cap at 30, specific recommendation IDs at four, and chat history reload at 50 rows. The frontend times out a chat request after 60 seconds and shows an error; it does not fabricate an answer.

### Safety and privacy rules

The system prompt makes the model use tools for descriptions, price, color, and stock. It must state zero stock clearly, distinguish an unlisted size from zero, and disclose a failed or missing lookup rather than guess. It treats shopper text and catalogue fields as untrusted; embedded requests to reveal instructions, secrets, or other customers' data are ignored. It must not ask for passwords or expose hashes, tokens, keys, or private records. Identity comes only from the verified session and is not passed into product searches. The agent cannot promise checkout, payment, reservations, shipping, discounts, or future stock because no tool implements those actions. Out-of-scope questions receive a brief scope explanation. FastAPI validates chat lengths and page context, verifies product IDs, checks the allowed origin on writes, and shows source failures visibly. Account passwords and sessions follow the protections in the Problem 4 section.

Signed-in customer name and email are included in the external Portkey model request for personalization; the database, hashes, and cookie tokens are not. `backend/audit.py` avoids raw chat text and identity in its JSON audit events. Every event has UTC `time`, `tool_name`, short `arguments` and `result` summaries, and `stop_reason` (`tool_returned`, `tool_error`, `completed`, or `error`). Tool wrappers log calls and outcomes; the agent loop logs completion or failure. The JSON array is loaded and extended under a process lock, then replaced atomically, preserving earlier events between runs. The file lives at `output/audit_trail.json` and is part of the submission; it contains no API key or raw messages. A normal one-worker local server is assumed for the process-level lock.

### Running and checking the shop

Put the supplied `campus_customs.db` and `products/` inside the local, Git-ignored `data/` folder. From the project root, create a Python environment and install `requirements.txt`. Set `PORTKEY_API_KEY` in the environment or ignored `.env`; use placeholder-only `.env.example` for reference. Start FastAPI from `backend/` with `uvicorn main:app --reload --port 8000`. In a second terminal, run `npm install` and `npm run dev` from `frontend/`, then open `http://127.0.0.1:5173`. Vite proxies `/api` to port 8000; if that port is occupied, set `VITE_API_TARGET` in ignored `frontend/.env.local` to the actual backend URL. The API exposes `/api/health`, `/api/products`, product detail/image routes, account routes, `/api/chat`, and authenticated `/api/chat/history`. The product API works without Portkey; chat reports a visible error if Portkey or the local catalogue is unavailable. `README.md` gives the complete local commands.

Verification: two audit tool events were recorded in separate Python processes, and the second run preserved the first. A live Portkey chat then added stock and product lookup events plus an `agent_loop` completion event; its answer matched the database's five Medium units and $68 price for Basic Hoodie Big Yale. The frontend production build passed. `output/app_check.html` documents live price/stock chat, 27 hoodie cards from a category question, and the XS stock filter with price sorting; its three screenshots use relative paths inside `output/app_check_images/`.
