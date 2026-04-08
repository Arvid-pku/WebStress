"""Composable seed builder framework for the Amazon shopping environment.

Provides :class:`AmazonSeedContext` (the mutable accumulator threaded through
every builder step) and a registry of reusable builder functions that generate
deterministic test data for Amazon benchmark tasks.
"""

from __future__ import annotations

import hashlib
import random
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Callable

from webagentbench.backend.models.amazon import (
    Address,
    CartItem,
    Order,
    OrderItem,
    PaymentMethod,
    Product,
    ProductVariant,
    Review,
)


# ---------------------------------------------------------------------------
# Category-specific product data
# ---------------------------------------------------------------------------

_CATEGORY_DATA: dict[str, dict[str, Any]] = {
    "Electronics": {
        "subcategories": [
            "Headphones", "Chargers", "Smart Home", "Speakers", "Cables",
            "Webcams", "Keyboards", "Mice", "Hubs & Adapters", "Earbuds",
        ],
        "brands": [
            "Voltrex", "SoundCore", "Lumivox", "TechNova", "Circuitry",
            "Pixelon", "Wavefront", "ChargeMax", "NexGen Audio", "VoltEdge",
        ],
        "templates": [
            "Wireless Noise-Cancelling Over-Ear {sub}",
            "65W GaN USB-C Fast {sub} 3-Port",
            "Smart Wi-Fi LED Light Bulb 4-Pack",
            "Portable Bluetooth 5.3 {sub} IPX7 Waterproof",
            "1080p {sub} with Ring Light and Dual Microphone",
            "Mechanical Gaming {sub} RGB Backlit",
            "Wireless Ergonomic {sub} 2.4GHz",
            "4K HDMI Cable 6ft High Speed Braided",
            "USB-C Hub 7-in-1 Multiport Adapter",
            "True Wireless {sub} Active Noise Cancelling",
            "{brand} {adj} Wireless Bluetooth {sub}",
            "{brand} {adj} USB-C {sub}",
            "{brand} {adj} Noise-Cancelling {sub}",
            "{brand} {adj} Portable {sub}",
            "{brand} {adj} {sub} with Charging Case",
            "Ultra-Slim {adj} {sub} with Touch Controls",
            "{brand} {adj} 4K HDMI 2.1 {sub} 10ft Braided",
            "{brand} {adj} Smart {sub} with Voice Control",
        ],
        "adjectives": [
            "Pro", "Ultra", "Elite", "Essential", "Compact",
            "Plus", "Max", "Slim", "Turbo", "Precision",
        ],
        "features": [
            "Up to 30 hours battery life",
            "Active noise cancellation with transparency mode",
            "IPX7 water and sweat resistance",
            "Quick charge: 10 minutes for 2 hours playback",
            "Built-in microphone with echo cancellation",
            "Bluetooth 5.3 with multipoint connectivity",
            "USB-C and USB-A dual compatibility",
            "Memory foam ear cushions for all-day comfort",
            "Hi-Res Audio certified with LDAC support",
            "Foldable design with carrying case included",
            "Touch controls for volume and track skipping",
            "Auto-pause when removed from ears",
        ],
        "desc_templates": [
            "Experience crystal-clear audio with advanced {adj} technology. Features {feat1} and {feat2} for an immersive listening experience that keeps up with your lifestyle.",
            "Engineered for peak performance with {feat1}. The {adj} design ensures reliability whether you are at your desk or on the go, backed by {feat2}.",
            "Take your setup to the next level with this {adj} device featuring {feat1}. Compact enough for travel yet powerful enough for daily use, with {feat2} built in.",
        ],
    },
    "Books": {
        "subcategories": [
            "Business & Leadership", "Psychology & Behavior",
            "Technology & Programming", "Personal Development",
            "Science & Nature", "History & Politics",
            "Health & Wellness", "Fiction & Literature",
        ],
        "brands": [
            "Birchwood Press", "Northstar Publishing", "Clearview Books",
            "Summit House", "Ridgeline Press", "Ironwood Publishers",
            "Lakeside Literary", "Hearthstone Books", "Windmill Press",
            "Copperfield & Co.",
        ],
        "templates": [
            "The Psychology of {noun}",
            "Modern {sub} Patterns",
            "{noun} That Stick: A Practical Guide",
            "The Data-Driven {noun}",
            "Mindful {noun} in the Digital Age",
            "Introduction to {sub} with Python",
            "The Art of Strategic {noun}",
            "Financial Independence Roadmap",
            "The {adj} Mind: Rewiring {noun} for Success",
            "Deep Work and the {adj} Professional",
            "Atomic {noun}: Small Changes, Big Results",
            "The {adj} Leader's Playbook",
            "Thinking in {noun}: A Framework for {sub}",
            "From Zero to {adj}: A {sub} Story",
            "The {noun} Effect: Why {adj} People Succeed",
            "Quiet {noun}: The Power of {adj} Thinking",
        ],
        "adjectives": [
            "Silent", "Infinite", "Hidden", "Resilient", "Forgotten",
            "Deliberate", "Effortless", "Radical", "Fearless", "Intentional",
        ],
        "nouns": [
            "Habits", "Decision Making", "Leadership", "Productivity",
            "Innovation", "Influence", "Complexity", "Momentum",
            "Focus", "Strategy",
        ],
        "features": [
            "Hardcover edition with dust jacket",
            "National bestseller with over 1 million copies sold",
            "Includes 12 actionable worksheets and exercises",
            "Foreword by a leading industry expert",
            "Companion website with bonus resources",
            "Over 350 pages with illustrations and charts",
            "Includes reading group discussion guide",
            "Endorsed by top CEOs and thought leaders",
            "Available in large print and audiobook formats",
            "Index and bibliography with 200+ references",
        ],
        "desc_templates": [
            "A comprehensive guide to mastering {noun} in both personal and professional life. Packed with actionable strategies, real-world case studies, and practical exercises drawn from decades of research.",
            "Explore the science behind {noun} and discover why conventional wisdom often falls short. This thought-provoking book combines cutting-edge research with compelling stories that will change how you approach every day.",
            "Whether you are a seasoned professional or just starting out, this book offers a fresh perspective on {noun}. Readers will find step-by-step frameworks, memorable examples, and tools they can apply immediately.",
        ],
    },
    "Home & Kitchen": {
        "subcategories": [
            "Cookware & Bakeware", "Food Storage & Organization",
            "Kitchen Utensils & Gadgets", "Drinkware & Water Bottles",
            "Bedding & Linens", "Home Decor & Accents",
            "Cleaning Supplies", "Small Appliances",
        ],
        "brands": [
            "Ironstone Home", "CedarCraft", "PureVessel", "Hearthway",
            "Stonemill Kitchen", "Aquaterra", "MapleLine", "NestWell",
            "BrightHearth", "CopperRidge",
        ],
        "templates": [
            "32oz Vacuum Insulated Stainless Steel {sub}",
            "12-Inch Non-Stick Ceramic {sub}",
            "Bamboo {sub} Set of 3 with Juice Groove",
            "Electric Gooseneck {sub} Temperature Control",
            "Silicone {sub} Set 12-Piece Heat Resistant",
            "Glass Airtight {sub} 18-Piece Set",
            "Cast Iron Dutch Oven 6-Quart Pre-Seasoned",
            "Stainless Steel Mixing Bowl Set with Lids",
            "{brand} {adj} {sub} Set",
            "{brand} {adj} Stainless Steel {sub}",
            "{brand} {adj} Non-Stick {sub}",
            "{brand} Premium {adj} {sub}",
            "{brand} {adj} Insulated {sub} with Lid",
            "{brand} {adj} Bamboo {sub} with Storage",
            "8-Piece {adj} {sub} Collection Non-Toxic",
            "{brand} {adj} Glass {sub} with Snap-Lock Lids",
            "Double-Wall Insulated {sub} Set of 4",
            "{brand} {adj} Silicone {sub} BPA-Free",
        ],
        "adjectives": [
            "Professional", "Deluxe", "Classic", "Modern", "Everyday",
            "Heritage", "Artisan", "Signature", "Rustic", "Premium",
        ],
        "features": [
            "Dishwasher safe for easy cleanup",
            "100% BPA-free and food-grade materials",
            "Lifetime manufacturer warranty",
            "Heat resistant up to 450F / 232C",
            "Ergonomic soft-grip handle for comfort",
            "Stackable design saves cabinet space",
            "Compatible with all cooktops including induction",
            "PFOA-free non-stick coating",
            "Double-wall vacuum insulation keeps drinks cold 24 hours",
            "Includes matching lids for airtight storage",
            "Sustainably sourced bamboo construction",
            "Stain and odor resistant surface",
        ],
        "desc_templates": [
            "Upgrade your kitchen with this {adj} {sub} built from premium materials. Features {feat1} and {feat2}, making meal prep faster and cleanup effortless.",
            "Designed for home cooks who demand quality, this {adj} {sub} delivers professional-grade performance. Enjoy {feat1} along with {feat2} for years of reliable use.",
            "From weeknight dinners to weekend entertaining, this {adj} {sub} is up to the task. Built with {feat1} and finished with {feat2} so it looks as good as it performs.",
        ],
    },
    "Clothing": {
        "subcategories": [
            "Men's T-Shirts & Polos", "Women's Tops & Blouses",
            "Jackets & Outerwear", "Pants & Chinos",
            "Athletic & Activewear", "Socks & Underwear",
            "Dresses & Skirts", "Sweaters & Pullovers",
        ],
        "brands": [
            "TrailMark", "UrbanStride", "FitEdge", "SummitWear",
            "Everthread", "CoastLine", "RidgeCrest", "PureMotion",
            "WoolHaven", "IronThread",
        ],
        "templates": [
            "Men's Classic-Fit Cotton Crew {sub} 3-Pack",
            "Women's Quick-Dry Running {sub} 5-Inch",
            "Lightweight Packable Puffer {sub} Water Resistant",
            "Stretch Slim-Fit Chino {sub}",
            "Merino Wool Blend Crew {sub} 6-Pack",
            "Men's Fleece Quarter-Zip {sub}",
            "Women's High-Waist Yoga {sub} with Pockets",
            "{brand} {adj} {sub} for Men",
            "{brand} {adj} {sub} for Women",
            "{brand} {adj} Athletic {sub}",
            "{brand} {adj} Casual {sub}",
            "{brand} {adj} Performance {sub} Moisture-Wicking",
            "Men's {adj} Stretch {sub} Relaxed Fit",
            "Women's {adj} Breathable {sub} UPF 50+",
            "{brand} {adj} Insulated {sub} with Hood",
            "Unisex {adj} Comfort {sub} Tag-Free",
        ],
        "adjectives": [
            "Performance", "Premium", "Lightweight", "Stretch", "Classic",
            "All-Season", "Relaxed", "Tailored", "Breathable", "Durable",
        ],
        "features": [
            "Machine washable and tumble dry low",
            "Moisture-wicking fabric keeps you dry",
            "4-way stretch for unrestricted movement",
            "UPF 50+ sun protection built in",
            "Reflective details for low-light visibility",
            "Available in 12 colors and extended sizes",
            "Tag-free interior for itch-free comfort",
            "Reinforced double-stitched seams",
            "Quick-dry technology for active use",
            "Pre-shrunk ring-spun cotton",
            "Zippered side pockets for secure storage",
            "Flatlock seams reduce chafing during workouts",
        ],
        "desc_templates": [
            "Built for comfort and style, this {adj} {sub} features {feat1} and {feat2}. Perfect for everything from casual weekends to active adventures.",
            "Stay comfortable all day with this {adj} {sub} crafted from {feat1}. Designed with {feat2} so you can move freely without compromising on looks.",
            "A wardrobe essential that combines everyday versatility with {adj} construction. Enjoy {feat1} and {feat2} in a fit that flatters every body type.",
        ],
    },
    "Sports & Outdoors": {
        "subcategories": [
            "Yoga & Pilates", "Strength Training", "Resistance & Bands",
            "Hiking & Backpacking", "Hydration & Water Bottles",
            "Recovery & Foam Rollers", "Camping & Hammocks",
            "Headlamps & Lighting",
        ],
        "brands": [
            "SummitForge", "TrailVista", "IronPeak", "BaseEdge",
            "RapidStrike", "AlpineCore", "Endurafit", "WildPath",
            "TerraPulse", "Bouldercraft",
        ],
        "templates": [
            "Extra Thick 1/2-Inch Yoga Mat with Carrying Strap",
            "Adjustable Dumbbell Set 5-25 lbs",
            "Resistance Bands Set of 5 with Door Anchor",
            "40L Waterproof {sub} Backpack with Rain Cover",
            "Collapsible 32oz {sub} BPA-Free",
            "High-Density Foam Roller 18-Inch",
            "USB Rechargeable LED {sub} 1000 Lumens",
            "Double Camping {sub} with Tree Straps",
            "{brand} {adj} {sub} Gear",
            "{brand} {adj} Outdoor {sub}",
            "{brand} {adj} Trail {sub}",
            "{brand} {adj} Adventure {sub}",
            "{brand} {adj} {sub} with Carrying Case",
            "Insulated {adj} {sub} with Bite Valve 24oz",
            "{brand} {adj} Quick-Deploy {sub} for Camping",
            "Anti-Burst Exercise Ball 65cm with Pump",
            "{brand} {adj} {sub} Set with Workout Guide",
            "Ultralight {adj} {sub} Carbon Fiber Poles",
        ],
        "adjectives": [
            "Explorer", "Summit", "Trailblazer", "Endurance", "Basecamp",
            "Apex", "Rugged", "Ultralight", "All-Terrain", "ProGrip",
        ],
        "features": [
            "Lightweight and packable under 2 lbs",
            "Waterproof IPX6-rated construction",
            "Adjustable padded straps and buckles",
            "Durable 40D ripstop nylon shell",
            "Includes carrying case and carabiner",
            "Tested in extreme alpine conditions",
            "Non-slip textured surface for grip",
            "Eco-friendly recycled materials",
            "Reflective accents for nighttime visibility",
            "Quick-release buckles for fast setup",
            "Ergonomic design reduces joint strain",
            "Lifetime warranty against manufacturing defects",
        ],
        "desc_templates": [
            "Push your limits with this {adj} {sub} designed for serious athletes and weekend warriors alike. Features {feat1} and {feat2} to keep you performing at your best.",
            "Whether you are hitting the trail or the gym, this {adj} {sub} delivers with {feat1}. Compact and travel-friendly, plus {feat2} for added durability.",
            "Gear up for any adventure with this {adj} {sub}. Engineered with {feat1} and {feat2}, it is built to handle the toughest conditions you can throw at it.",
        ],
    },
    "Health & Beauty": {
        "subcategories": [
            "Facial Serums & Treatments", "Hair Care & Styling",
            "Oral Care & Toothbrushes", "Moisturizers & SPF",
            "Supplements & Vitamins", "Body Care & Lotions",
            "Grooming Tools", "Natural & Organic",
        ],
        "brands": [
            "PureGlow", "Dermatica", "VitaBloom", "ClearSkin Labs",
            "NaturVive", "RadiantEssence", "HydraLux", "BotanaVita",
            "ZenDerm", "HelixHealth",
        ],
        "templates": [
            "Vitamin C Brightening Serum with Hyaluronic Acid",
            "Sonic Electric Toothbrush with 4 Brush Heads",
            "Daily Moisturizing Face Cream SPF 30",
            "Argan Oil Repair Conditioner for Damaged Hair",
            "Mineral Sunscreen Lotion SPF 50 Reef Safe",
            "Retinol Night Cream Anti-Aging 2oz",
            "Biotin Hair Growth Supplement 10000mcg 90 Caps",
            "{brand} {adj} {sub} Treatment",
            "{brand} {adj} Daily {sub}",
            "{brand} {adj} Hydrating {sub}",
            "{brand} {adj} Renewing {sub}",
            "{brand} {adj} {sub} with Niacinamide 1oz",
            "Collagen Peptides Powder Unflavored 20oz",
            "{brand} {adj} Exfoliating {sub} AHA/BHA",
            "Activated Charcoal {adj} {sub} Deep Cleanse",
            "{brand} {adj} Probiotic {sub} 60 Capsules",
        ],
        "adjectives": [
            "Advanced", "Clinical", "Natural", "Intensive", "Gentle",
            "Ultra-Repair", "Revitalizing", "Clarifying", "Soothing", "Brightening",
        ],
        "features": [
            "Dermatologist tested and recommended",
            "Fragrance-free hypoallergenic formula",
            "Non-comedogenic, won't clog pores",
            "Paraben-free and sulfate-free",
            "Suitable for all skin types including sensitive",
            "Broad spectrum SPF 30 protection",
            "Cruelty-free and vegan certified",
            "Contains antioxidant-rich botanical extracts",
            "Clinically proven results in 4 weeks",
            "Recyclable packaging made from post-consumer resin",
            "Enriched with vitamins C and E",
            "pH-balanced for skin barrier support",
        ],
        "desc_templates": [
            "Reveal your best skin with this {adj} formula powered by {feat1}. Lightweight and fast-absorbing, it delivers {feat2} for a visibly radiant complexion.",
            "Backed by clinical research, this {adj} product features {feat1} and {feat2}. Suitable for daily use and gentle enough for even the most sensitive skin.",
            "Transform your routine with this {adj} treatment combining {feat1} with {feat2}. Customers report noticeable results in as little as two weeks of consistent use.",
        ],
    },
    "Toys & Games": {
        "subcategories": [
            "Jigsaw Puzzles", "Building Blocks & Sets", "Strategy Board Games",
            "Remote Control Vehicles", "Science & STEM Kits",
            "Magnetic Building Tiles", "Card Games & Family Games",
            "Wooden Toys & Train Sets",
        ],
        "brands": [
            "BlockCraft", "PuzzleMaster", "WonderBuild", "MindSpark",
            "PlayForge", "BrightBricks", "StackWorld", "GameHaven",
            "TinkerLab", "KidGenius",
        ],
        "templates": [
            "1000-Piece Gradient Rainbow Jigsaw Puzzle",
            "STEM Building Blocks Mega Set 500 Pieces",
            "Strategy Board Game for Adults and Teens",
            "2.4GHz Remote Control Monster Truck 4WD",
            "Kids Science Experiment Kit 30+ Projects",
            "Magnetic Tile Building Set 100 Pieces",
            "Family Card Game Collection 5-in-1",
            "Wooden Train Track Set 80 Pieces Compatible",
            "{brand} {adj} {sub} Collection",
            "{brand} {adj} {sub} Playset",
            "{brand} {adj} {sub} Challenge",
            "{brand} {adj} Creative {sub}",
            "{brand} {adj} {sub} for Ages 8-12",
            "Glow-in-the-Dark {adj} {sub} Set",
            "{brand} {adj} Robotics {sub} Kit",
            "Giant Floor {sub} 48 Pieces Ages 3+",
            "{brand} {adj} Cooperative {sub} for Families",
            "3D Crystal {sub} with LED Light Base",
        ],
        "adjectives": [
            "Ultimate", "Mega", "Classic", "Deluxe", "Junior",
            "Advanced", "Explorer", "Epic", "Super", "Genius",
        ],
        "features": [
            "Recommended for ages 6 and up",
            "2-6 players for group fun",
            "Full-color illustrated instruction manual",
            "STEM / STEAM learning certified",
            "Over 500 pieces in the set",
            "Award-winning design (Parents' Choice Gold)",
            "Made from non-toxic ABS plastic",
            "Rechargeable battery with USB-C cable",
            "Compatible with all major building brick brands",
            "Storage container included for easy cleanup",
            "Develops critical thinking and motor skills",
            "Durable construction withstands rough play",
        ],
        "desc_templates": [
            "Spark imagination and creativity with this {adj} {sub} set. Features {feat1} and {feat2}, providing hours of screen-free entertainment for the whole family.",
            "Designed to educate and entertain, this {adj} {sub} comes with {feat1}. Perfect for birthday gifts and rainy-day fun, plus {feat2} for lasting value.",
            "Kids and adults alike will love this {adj} {sub} offering {feat1} and {feat2}. Encourages collaborative play and keeps everyone engaged from start to finish.",
        ],
    },
    "Office Supplies": {
        "subcategories": [
            "Desk Chairs & Seating", "Standing Desks & Converters",
            "Desk Lamps & Lighting", "Cable Management",
            "Monitor Arms & Mounts", "Desk Organizers",
            "Keyboards & Accessories", "Whiteboards & Boards",
        ],
        "brands": [
            "DeskPro", "ErgoNest", "ClearView Office", "PosturePlus",
            "LuminDesk", "MountRight", "CableNeat", "WorkStation Co.",
            "StandWell", "GridLine",
        ],
        "templates": [
            "Ergonomic Mesh Office Chair Lumbar Support",
            "Standing Desk Converter 36-Inch Adjustable",
            "Wireless Mechanical Keyboard Low Profile",
            "LED Desk Lamp with USB Charging Port",
            "Noise-Cancelling Desk Divider Panel Set",
            "Cable Management Box Large White",
            "Monitor Arm Mount Single 13-32 Inch",
            "{brand} {adj} {sub} with Adjustable Height",
            "{brand} {adj} {sub} Organizer 5-Compartment",
            "{brand} {adj} Ergonomic {sub}",
            "{brand} {adj} {sub} with Clamp Mount",
            "Magnetic Dry Erase Whiteboard 36x24 Inch",
            "{brand} {adj} Laptop {sub} with Cooling Vents",
            "{brand} {adj} Under-Desk {sub} Tray",
            "Acoustic {adj} {sub} Panel Set of 6",
            "{brand} {adj} Dual Monitor {sub} Arm",
        ],
        "adjectives": [
            "Professional", "Executive", "Ergonomic", "Adjustable", "Sleek",
            "Space-Saving", "Premium", "Minimalist", "Heavy-Duty", "Compact",
        ],
        "features": [
            "Adjustable lumbar support and headrest",
            "360-degree swivel with smooth-rolling casters",
            "Gas lift height adjustment 16-20 inches",
            "Supports monitors up to 32 inches and 20 lbs",
            "Built-in USB-A and USB-C charging ports",
            "Tool-free assembly in under 15 minutes",
            "Cable routing channels for a clean look",
            "BIFMA certified for commercial use",
            "Breathable mesh back promotes airflow",
            "Non-slip rubber feet protect desk surfaces",
            "Tilt, swivel, and rotate for perfect positioning",
            "Weight capacity up to 300 lbs",
        ],
        "desc_templates": [
            "Create a more productive workspace with this {adj} {sub}. Engineered with {feat1} and {feat2}, it transforms any desk into an ergonomic command center.",
            "Work smarter and more comfortably with this {adj} {sub} featuring {feat1}. Easy to install and built to last, with {feat2} for a polished, professional look.",
            "Designed for the modern home office, this {adj} {sub} combines form and function. Enjoy {feat1} alongside {feat2} for all-day comfort and efficiency.",
        ],
    },
}

_DELIVERY_ESTIMATES_PRIME = [
    "Tomorrow by 9 PM",
    "Tomorrow by end of day",
    "Next-day delivery",
    "1-2 business days",
    "2-day shipping",
]

_DELIVERY_ESTIMATES_STANDARD = [
    "3-5 business days",
    "5-7 business days",
    "1 week",
    "7-10 business days",
    "2 weeks",
]

_REVIEW_BODIES_POSITIVE = [
    "Excellent quality and fast shipping. Exactly what I was looking for.",
    "Works great right out of the box. Very happy with this purchase.",
    "Solid build quality. Exceeded my expectations for the price.",
    "Been using this for a few weeks and it holds up really well.",
    "Perfect gift idea. The recipient loved it.",
]

_REVIEW_BODIES_NEUTRAL = [
    "Decent product for the price, though nothing spectacular.",
    "It does the job. A few minor quirks but overall acceptable.",
    "Arrived on time. Quality is average but works as described.",
]

_REVIEW_BODIES_NEGATIVE = [
    "Stopped working after two weeks. Disappointed with the durability.",
    "Not as described. The size was smaller than I expected.",
    "Poor packaging led to damage during shipping. Had to return.",
]

_REVIEWER_NAMES = [
    "Alex M.", "Jordan K.", "Taylor S.", "Morgan L.", "Casey R.",
    "Riley P.", "Avery D.", "Quinn T.", "Parker W.", "Drew H.",
    "Jamie N.", "Skyler B.", "Finley C.", "Rowan G.", "Emerson J.",
]


# ---------------------------------------------------------------------------
# AmazonSeedContext
# ---------------------------------------------------------------------------

@dataclass
class AmazonSeedContext:
    """Mutable accumulator threaded through every Amazon seed builder step.

    Exposes shared helpers such as ``ctx.product()`` and ``ctx.cart_item()``
    so builders can operate against one deterministic state interface.
    """

    seed: int
    rng: random.Random
    fake: Any  # FakeDataGenerator
    now: datetime
    base: dict[str, Any]
    actors: dict[str, Any] = field(default_factory=dict)
    outputs: dict[str, Any] = field(default_factory=dict)
    counters: dict[str, int] = field(default_factory=lambda: defaultdict(int))

    def __post_init__(self) -> None:
        self.owner_name: str = self.base.get("owner_name", "Avery Quinn")
        self.owner_email: str = self.base.get("owner_email", "avery.quinn@example.com")

    # -- ID generation -----------------------------------------------------

    def next_id(self, prefix: str) -> str:
        """Return a monotonically increasing id like ``product_1``."""
        self.counters[prefix] += 1
        return f"{prefix}_{self.counters[prefix]}"

    # -- Model factories ---------------------------------------------------

    def product(
        self,
        *,
        name: str | None = None,
        brand: str | None = None,
        category: str = "Electronics",
        subcategory: str | None = None,
        description: str | None = None,
        price: float | None = None,
        list_price: float | None = None,
        rating: float | None = None,
        review_count: int | None = None,
        in_stock: bool = True,
        stock_quantity: int = 100,
        features: list[str] | None = None,
        variants: list[ProductVariant] | None = None,
        seller: str = "Amazon.com",
        prime_eligible: bool = True,
        delivery_estimate: str | None = None,
        image_url: str | None = None,
    ) -> Product:
        cat_data = _CATEGORY_DATA.get(category, _CATEGORY_DATA["Electronics"])
        sub = subcategory or self.rng.choice(cat_data["subcategories"])
        chosen_brand = brand or self.rng.choice(cat_data["brands"])

        if name is None:
            template = self.rng.choice(cat_data["templates"])
            adj = self.rng.choice(cat_data["adjectives"])
            fmt_kwargs: dict[str, str] = {
                "brand": chosen_brand,
                "adj": adj,
                "sub": sub,
            }
            if "{noun}" in template:
                fmt_kwargs["noun"] = self.rng.choice(cat_data.get("nouns", ["Item"]))
            name = template.format(**fmt_kwargs)

        if price is None:
            price = round(self.rng.uniform(9.99, 199.99), 2)

        if description is None:
            desc_templates = cat_data.get("desc_templates")
            if desc_templates:
                adj = self.rng.choice(cat_data["adjectives"])
                pool = cat_data.get("features", [])
                feat1 = self.rng.choice(pool) if pool else "premium materials"
                remaining = [f for f in pool if f != feat1]
                feat2 = self.rng.choice(remaining) if remaining else "attention to detail"
                # Books use {noun} instead of {sub}
                fmt_kwargs_desc: dict[str, str] = {
                    "adj": adj.lower(),
                    "sub": sub.lower(),
                    "feat1": feat1.lower(),
                    "feat2": feat2.lower(),
                    "brand": chosen_brand,
                }
                if "nouns" in cat_data:
                    fmt_kwargs_desc["noun"] = self.rng.choice(cat_data["nouns"]).lower()
                template_desc = self.rng.choice(desc_templates)
                try:
                    description = template_desc.format(**fmt_kwargs_desc)
                except KeyError:
                    description = (
                        f"High-quality {sub.lower()} from {chosen_brand}. "
                        f"Designed for everyday use with premium materials "
                        f"and attention to detail."
                    )
            else:
                description = (
                    f"High-quality {sub.lower()} from {chosen_brand}. "
                    f"Designed for everyday use with premium materials and "
                    f"attention to detail."
                )

        if features is None:
            pool = cat_data.get("features", [])
            features = self.rng.sample(pool, k=min(3, len(pool)))

        return Product(
            id=self.next_id("product"),
            name=name,
            brand=chosen_brand,
            category=category,
            subcategory=sub,
            description=description,
            price=price,
            list_price=list_price,
            currency="USD",
            rating=rating if rating is not None else round(self.rng.uniform(3.0, 5.0), 1),
            review_count=review_count if review_count is not None else self.rng.randint(10, 5000),
            in_stock=in_stock,
            stock_quantity=stock_quantity,
            image_url=image_url or f"https://picsum.photos/seed/{hashlib.md5(name.encode()).hexdigest()[:8]}/400/400",
            features=features,
            variants=variants or [],
            seller=seller,
            prime_eligible=prime_eligible,
            delivery_estimate=delivery_estimate or self.rng.choice(
                _DELIVERY_ESTIMATES_PRIME if prime_eligible else _DELIVERY_ESTIMATES_STANDARD
            ),
        )

    def cart_item(
        self,
        product: Product,
        quantity: int = 1,
        *,
        variant_selections: dict[str, str] | None = None,
    ) -> CartItem:
        return CartItem(
            id=self.next_id("cart"),
            product_id=product.id,
            product_name=product.name,
            quantity=quantity,
            unit_price=product.price,
            variant_selections=variant_selections or {},
            added_at=self.now - timedelta(hours=self.rng.randint(1, 48)),
        )

    def review(
        self,
        product_id: str,
        *,
        author_name: str | None = None,
        rating: int | None = None,
        title: str | None = None,
        body: str | None = None,
        helpful_count: int | None = None,
        verified_purchase: bool = True,
        days_ago: int | None = None,
    ) -> Review:
        r = rating if rating is not None else self.rng.randint(1, 5)
        if body is None:
            if r >= 4:
                body = self.rng.choice(_REVIEW_BODIES_POSITIVE)
            elif r >= 3:
                body = self.rng.choice(_REVIEW_BODIES_NEUTRAL)
            else:
                body = self.rng.choice(_REVIEW_BODIES_NEGATIVE)
        if title is None:
            if r >= 4:
                title = self.rng.choice(["Great product!", "Highly recommend", "Love it", "Five stars"])
            elif r >= 3:
                title = self.rng.choice(["It's okay", "Decent", "Gets the job done", "Average"])
            else:
                title = self.rng.choice(["Disappointed", "Not worth it", "Could be better", "Returned"])

        return Review(
            id=self.next_id("review"),
            product_id=product_id,
            author_name=author_name or self.rng.choice(_REVIEWER_NAMES),
            rating=r,
            title=title,
            body=body,
            helpful_count=helpful_count if helpful_count is not None else self.rng.randint(0, 120),
            verified_purchase=verified_purchase,
            created_at=self.now - timedelta(days=days_ago or self.rng.randint(1, 180)),
        )

    def address(
        self,
        *,
        full_name: str | None = None,
        is_default: bool = False,
    ) -> Address:
        return Address(
            id=self.next_id("addr"),
            full_name=full_name or self.owner_name,
            street_address=self.fake.street_address(),
            city=self.fake.city(),
            state=self.fake.state_abbr(),
            zip_code=self.fake.zipcode(),
            country="United States",
            is_default=is_default,
            phone=self.fake.phone_number(),
        )

    def payment_method(
        self,
        *,
        holder_name: str | None = None,
        is_default: bool = False,
    ) -> PaymentMethod:
        card_types = ["Visa", "Mastercard", "American Express", "Discover"]
        return PaymentMethod(
            id=self.next_id("pay"),
            card_type=self.rng.choice(card_types),
            last_four=f"{self.rng.randint(1000, 9999)}",
            expiry=f"{self.rng.randint(1, 12):02d}/{self.rng.randint(2026, 2030)}",
            holder_name=holder_name or self.owner_name,
            is_default=is_default,
        )

    def order(
        self,
        *,
        items: list[OrderItem],
        shipping_address_id: str,
        payment_method_id: str,
        status: str = "delivered",
        days_ago: int = 7,
        promo_code: str | None = None,
        discount: float = 0.0,
    ) -> Order:
        subtotal = round(sum(i.unit_price * i.quantity for i in items), 2)
        tax = round(subtotal * 0.08, 2)
        total = round(subtotal + tax - discount, 2)
        return Order(
            id=self.next_id("order"),
            items=items,
            shipping_address_id=shipping_address_id,
            payment_method_id=payment_method_id,
            subtotal=subtotal,
            shipping_cost=0.0,
            tax=tax,
            total=total,
            status=status,
            placed_at=self.now - timedelta(days=days_ago),
            estimated_delivery="Delivered" if status == "delivered" else "3-5 business days",
            promo_code=promo_code,
            discount=discount,
        )

    # -- Actor resolution --------------------------------------------------

    def resolve_actor(self, key: str, **kwargs: Any) -> dict[str, str]:
        """Generate a deterministic actor and cache it under *key*."""
        if key in self.actors:
            return self.actors[key]
        name = kwargs.get("name") or self.fake.name()
        actor = {
            "name": name,
            "email": f"{name.lower().replace(' ', '.')}@example.com",
        }
        self.actors[key] = actor
        return actor

    # -- Lookup helpers ----------------------------------------------------

    def get_product_by_id(self, product_id: str) -> Product | None:
        return next(
            (p for p in self.base["products"] if p.id == product_id), None
        )


# ---------------------------------------------------------------------------
# Builder registry
# ---------------------------------------------------------------------------

AmazonBuilderFn = Callable[["AmazonSeedContext", dict[str, Any]], dict[str, Any]]

AMAZON_BUILDER_REGISTRY: dict[str, AmazonBuilderFn] = {}


def _register(name: str) -> Callable[[AmazonBuilderFn], AmazonBuilderFn]:
    def decorator(fn: AmazonBuilderFn) -> AmazonBuilderFn:
        AMAZON_BUILDER_REGISTRY[name] = fn
        return fn
    return decorator


# ---------------------------------------------------------------------------
# Core builders
# ---------------------------------------------------------------------------

@_register("product_catalog")
def build_product_catalog(
    ctx: AmazonSeedContext, params: dict[str, Any]
) -> dict[str, Any]:
    """Create a set of products in a specific category.

    Params
    ------
    category : str              -- product category
    count : int                 -- number of products (default 5)
    price_range : [lo, hi]      -- uniform-random price range
    """
    category = params["category"]
    count = params.get("count", 5)
    lo, hi = params.get("price_range", [9.99, 199.99])

    product_ids: list[str] = []
    for _ in range(count):
        price = round(ctx.rng.uniform(lo, hi), 2)
        p = ctx.product(category=category, price=price)
        ctx.base["products"].append(p)
        product_ids.append(p.id)
    return {"product_ids": product_ids}


@_register("featured_product")
def build_featured_product(
    ctx: AmazonSeedContext, params: dict[str, Any]
) -> dict[str, Any]:
    """Create one specific product with detailed info for task scenarios.

    Params
    ------
    name : str
    brand : str
    category : str
    price : float
    rating : float              -- default 4.5
    features : list[str]        -- default []
    variants : list[dict]       -- [{name, value, price_modifier, in_stock}]
    in_stock : bool             -- default True
    subcategory : str | None
    description : str | None
    list_price : float | None
    review_count : int | None
    """
    variant_objects = [
        ProductVariant(
            name=v["name"],
            value=v["value"],
            price_modifier=v.get("price_modifier", 0.0),
            in_stock=v.get("in_stock", True),
        )
        for v in params.get("variants", [])
    ]

    p = ctx.product(
        name=params["name"],
        brand=params["brand"],
        category=params["category"],
        subcategory=params.get("subcategory"),
        description=params.get("description"),
        price=params["price"],
        list_price=params.get("list_price"),
        rating=params.get("rating", 4.5),
        review_count=params.get("review_count"),
        in_stock=params.get("in_stock", True),
        features=params.get("features", []),
        variants=variant_objects,
    )
    ctx.base["products"].append(p)
    return {
        "product_id": p.id,
        "product_name": p.name,
        "product_price": p.price,
        "product_list_price": p.list_price,
    }


@_register("pre_filled_cart")
def build_pre_filled_cart(
    ctx: AmazonSeedContext, params: dict[str, Any]
) -> dict[str, Any]:
    """Add specific products to the cart.

    Params
    ------
    product_ids : list[str]
    quantities : list[int]      -- parallel to product_ids (default all 1)
    """
    product_ids: list[str] = params["product_ids"]
    quantities: list[int] = params.get("quantities", [1] * len(product_ids))

    cart_item_ids: list[str] = []
    cart_total = 0.0
    for pid, qty in zip(product_ids, quantities, strict=False):
        product = ctx.get_product_by_id(pid)
        if product is None:
            continue
        item = ctx.cart_item(product, quantity=qty)
        ctx.base["cart_items"].append(item)
        cart_item_ids.append(item.id)
        cart_total += item.unit_price * item.quantity

    cart_total = round(cart_total, 2)
    return {"cart_item_ids": cart_item_ids, "cart_total": cart_total}


@_register("existing_order")
def build_existing_order(
    ctx: AmazonSeedContext, params: dict[str, Any]
) -> dict[str, Any]:
    """Create a past order for order-history scenarios.

    Params
    ------
    product_ids : list[str]
    status : str                -- e.g. "delivered", "shipped", "cancelled"
    days_ago : int              -- how many days in the past (default 7)
    """
    product_ids: list[str] = params["product_ids"]
    status = params.get("status", "delivered")
    days_ago = params.get("days_ago", 7)

    # Ensure at least one address and payment method exist
    if not ctx.base["addresses"]:
        addr = ctx.address(is_default=True)
        ctx.base["addresses"].append(addr)
    if not ctx.base["payment_methods"]:
        pm = ctx.payment_method(is_default=True)
        ctx.base["payment_methods"].append(pm)

    addr_id = ctx.base["addresses"][0].id
    pay_id = ctx.base["payment_methods"][0].id

    order_items: list[OrderItem] = []
    for pid in product_ids:
        product = ctx.get_product_by_id(pid)
        if product is None:
            continue
        order_items.append(
            OrderItem(
                product_id=product.id,
                product_name=product.name,
                quantity=1,
                unit_price=product.price,
            )
        )

    o = ctx.order(
        items=order_items,
        shipping_address_id=addr_id,
        payment_method_id=pay_id,
        status=status,
        days_ago=days_ago,
    )
    ctx.base["orders"].append(o)
    return {"order_id": o.id}


@_register("product_with_reviews")
def build_product_with_reviews(
    ctx: AmazonSeedContext, params: dict[str, Any]
) -> dict[str, Any]:
    """Create a product and add reviews.

    Params
    ------
    product_name : str
    category : str              -- default "Electronics"
    price : float               -- default 29.99
    brand : str | None
    rating : float | None
    reviews : list[dict]        -- [{rating, title, body}]
    """
    p = ctx.product(
        name=params["product_name"],
        category=params.get("category", "Electronics"),
        price=params.get("price", 29.99),
        brand=params.get("brand"),
        rating=params.get("rating"),
        review_count=len(params.get("reviews", [])),
    )
    ctx.base["products"].append(p)

    review_ids: list[str] = []
    for spec in params.get("reviews", []):
        r = ctx.review(
            p.id,
            rating=spec.get("rating"),
            title=spec.get("title"),
            body=spec.get("body"),
        )
        ctx.base["reviews"].append(r)
        review_ids.append(r.id)

    return {"product_id": p.id, "review_ids": review_ids}


@_register("wishlist_items")
def build_wishlist_items(
    ctx: AmazonSeedContext, params: dict[str, Any]
) -> dict[str, Any]:
    """Add products to the wishlist.

    Params
    ------
    product_ids : list[str]
    """
    for pid in params["product_ids"]:
        if pid not in ctx.base["wishlist"]:
            ctx.base["wishlist"].append(pid)
    return {}


@_register("checkout_ready")
def build_checkout_ready(
    ctx: AmazonSeedContext, params: dict[str, Any]
) -> dict[str, Any]:
    """Set up cart with items, address, and payment method ready for checkout.

    Params
    ------
    items : list[dict]          -- [{name, price, quantity, brand?, category?}]
    """
    items_spec: list[dict[str, Any]] = params["items"]

    # Create address if none exists
    if not ctx.base["addresses"]:
        addr = ctx.address(is_default=True)
        ctx.base["addresses"].append(addr)
    address_id = ctx.base["addresses"][0].id

    # Create payment method if none exists
    if not ctx.base["payment_methods"]:
        pm = ctx.payment_method(is_default=True)
        ctx.base["payment_methods"].append(pm)
    payment_id = ctx.base["payment_methods"][0].id

    cart_item_ids: list[str] = []
    expected_total = 0.0

    for spec in items_spec:
        p = ctx.product(
            name=spec["name"],
            price=spec["price"],
            brand=spec.get("brand"),
            category=spec.get("category", "Electronics"),
        )
        ctx.base["products"].append(p)

        qty = spec.get("quantity", 1)
        item = ctx.cart_item(p, quantity=qty)
        ctx.base["cart_items"].append(item)
        cart_item_ids.append(item.id)
        expected_total += p.price * qty

    expected_total = round(expected_total, 2)
    return {
        "cart_item_ids": cart_item_ids,
        "address_id": address_id,
        "payment_id": payment_id,
        "expected_total": expected_total,
    }


@_register("competitor_products")
def build_competitor_products(
    ctx: AmazonSeedContext, params: dict[str, Any]
) -> dict[str, Any]:
    """Add similar products to test comparison / decision-making.

    Params
    ------
    reference_product_id : str
    count : int                 -- number of competitors (default 3)
    price_variance : float      -- max fraction to vary price (default 0.2)
    """
    ref = ctx.get_product_by_id(params["reference_product_id"])
    if ref is None:
        return {"competitor_ids": []}

    count = params.get("count", 3)
    variance = params.get("price_variance", 0.2)

    cat_data = _CATEGORY_DATA.get(ref.category, _CATEGORY_DATA["Electronics"])
    # Pick brands different from the reference where possible
    other_brands = [b for b in cat_data["brands"] if b != ref.brand]
    if not other_brands:
        other_brands = cat_data["brands"]

    competitor_ids: list[str] = []
    for i in range(count):
        factor = 1.0 + ctx.rng.uniform(-variance, variance)
        comp_price = round(ref.price * factor, 2)
        comp_brand = other_brands[i % len(other_brands)]

        # Build a competing product name in the same subcategory
        adj = ctx.rng.choice(cat_data["adjectives"])
        comp_name = f"{comp_brand} {adj} {ref.subcategory}"

        p = ctx.product(
            name=comp_name,
            brand=comp_brand,
            category=ref.category,
            subcategory=ref.subcategory,
            price=comp_price,
        )
        ctx.base["products"].append(p)
        competitor_ids.append(p.id)

    return {"competitor_ids": competitor_ids}
