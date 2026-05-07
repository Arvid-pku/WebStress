import { useEffect, useState } from "react";
import { Link, useLocation } from "react-router-dom";
import { preserveQueryParams } from "@webstress/shared";

import type { Product } from "../types";
import { useAmazonLayout } from "../context";
import { ProductCard } from "../components/ProductCard";

const CATEGORIES = [
  { name: "Electronics", label: "Electronics", color: "#232f3e" },
  { name: "Books", label: "Books", color: "#3b4a5c" },
  { name: "Clothing", label: "Clothing", color: "#48647f" },
  { name: "Home & Kitchen", label: "Home", color: "#6e8ea8" },
  { name: "Sports & Outdoors", label: "Sports", color: "#3b6e5c" },
  { name: "Toys & Games", label: "Toys", color: "#8e5c3b" },
  { name: "Health & Beauty", label: "Beauty", color: "#8e3b6e" },
  { name: "Office Supplies", label: "Office", color: "#3b8e5c" },
];

export function HomePage() {
  const { api } = useAmazonLayout();
  const location = useLocation();
  const [featured, setFeatured] = useState<Product[]>([]);
  const [deals, setDeals] = useState<Product[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);

    Promise.all([
      api.getProducts({ page_size: 8, sort_by: "rating" }).catch(() => ({ items: [] as Product[] })),
      api.getProducts({ page_size: 8, sort_by: "price_low" }).catch(() => ({ items: [] as Product[] })),
    ]).then(([featuredResult, dealsResult]) => {
      if (cancelled) return;
      setFeatured(featuredResult.items ?? []);
      setDeals(dealsResult.items ?? []);
      setLoading(false);
    });

    return () => { cancelled = true; };
  }, [api]);

  return (
    <div className="home-page">
      {/* Hero banner */}
      <section className="home-hero" aria-label="Welcome banner">
        <div className="home-hero__content">
          <h1>Welcome to Amazon</h1>
          <p>Shop millions of products with fast delivery</p>
          <div className="home-hero__cta">
            <Link
              to={preserveQueryParams("/deals", location.search)}
              className="amazon-btn amazon-btn--add-to-cart home-hero__btn"
            >
              Shop Today's Deals
            </Link>
          </div>
        </div>
      </section>

      {/* Category grid */}
      <section className="home-categories" aria-label="Shop by category">
        <h2 className="home-section__title">Shop by Category</h2>
        <div className="home-categories__grid">
          {CATEGORIES.map((cat) => (
            <Link
              key={cat.name}
              to={preserveQueryParams(`/search?q=&category=${encodeURIComponent(cat.name)}`, location.search)}
              className="home-category-card"
              aria-label={`Browse ${cat.name}`}
            >
              <div className="home-category-card__square" style={{ backgroundColor: cat.color }}>
                <span className="home-category-card__square-text">{cat.label.charAt(0)}</span>
              </div>
              <span className="home-category-card__name">{cat.label}</span>
            </Link>
          ))}
        </div>
      </section>

      {/* Featured products */}
      {featured.length > 0 && (
        <section className="home-featured" aria-label="Featured products">
          <h2 className="home-section__title">Featured Products</h2>
          <div className="home-products__grid">
            {featured.map((product) => (
              <ProductCard key={product.id} product={product} />
            ))}
          </div>
        </section>
      )}

      {/* Deals */}
      {deals.length > 0 && (
        <section className="home-deals" aria-label="Today's deals">
          <div className="home-section__header">
            <h2 className="home-section__title">Top Deals</h2>
            <Link
              to={preserveQueryParams("/deals", location.search)}
              className="home-section__see-all"
            >
              See all deals
            </Link>
          </div>
          <div className="home-products__grid">
            {deals.map((product) => (
              <ProductCard key={product.id} product={product} />
            ))}
          </div>
        </section>
      )}

      {loading && (
        <div className="amazon-loading" aria-label="Loading products">
          <div className="amazon-spinner" />
          <p>Loading products...</p>
        </div>
      )}
    </div>
  );
}
