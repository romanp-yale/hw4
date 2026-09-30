# Campus Customs usability improvements (Problem 9)

This document records four implemented improvements and why each helps.

## Front end

1. **Catalogue sort and size availability controls.** The Products page now has name, low-price, and high-price ordering plus an “available in size” filter for XS–XXL. FastAPI derives `available_sizes` from inventory rows with positive quantities. Shoppers can narrow the catalogue to items available in their size and compare prices without opening each card.

2. **Related items on product pages.** Each detail page now shows up to four other products with the same `garment_type`, using the existing linked product cards. This gives shoppers a direct path to alternatives when the current item's color, fit, or stock is not right.

## Agent and backend

3. **Color-aware product lookup.** The agent now has `find_products_by_color(color, query, limit)`, a read-only tool that checks each catalogue product's actual `colors` list, then ranks any matching category terms. This prevents a broad name or tag match from being presented as proof that a color is offered and helps shoppers ask for a specific color confidently.

4. **Size-aware in-stock lookup.** The agent now has `find_in_stock_products(query, size, limit)`, a read-only tool that joins catalogue and inventory and returns only products with a positive quantity in the normalized requested size. The chatbot can recommend genuinely available size-specific alternatives instead of relying on a category match and guessing availability.

## Verification

The production frontend build passed. The catalogue API returned 102 products with database-derived available sizes. In the live browser, choosing XS reduced the catalogue to 75 products; high-to-low sorting put $98 items first. The Basic Hoodie Big Yale page showed four related hoodie cards, and clicking Crew Left Chest Hoodie opened its full detail view. Screenshots: `output/app_check_images/p9-catalogue.jpg` and `output/app_check_images/p9-related.jpg`.

Direct tool checks found eight navy-blue hoodie matches, no pink hoodie matches, and eight medium hoodies with positive M inventory in the first result page. Live guest chat correctly said there were no pink hoodies, and a medium-hoodie question returned grounded positive quantities and four product cards. The server was restarted with the new API and tools for the local running app.
