import { useEffect, useState } from "react";
import { Link, useLocation } from "react-router-dom";
import { preserveQueryParams } from "@webagentbench/shared";

import { useAmazonLayout } from "../context";

const CATEGORY_ICONS: Record<string, string> = {
  Electronics: "E",
  Books: "B",
  Clothing: "C",
  "Home & Kitchen": "H",
  Sports: "S",
  Toys: "T",
  Automotive: "A",
  Beauty: "Be",
  Garden: "G",
  Food: "F",
  Health: "He",
  Music: "M",
  Office: "O",
  Pet: "P",
  Tools: "To",
};

const CATEGORY_COLORS: string[] = [
  "#232f3e",
  "#e47911",
  "#007185",
  "#B12704",
  "#007600",
  "#00A8E1",
  "#c7511f",
  "#565959",
  "#131921",
  "#FFA41C",
  "#37475a",
  "#FF9900",
];

export function CategoriesPage() {
  const { api } = useAmazonLayout();
  const location = useLocation();
  const [categories, setCategories] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    api.getCategories()
      .then((cats) => {
        if (!cancelled) {
          setCategories(cats);
          setLoading(false);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setCategories([
            "Electronics", "Books", "Clothing", "Home & Kitchen",
            "Sports", "Toys", "Automotive", "Beauty",
            "Garden", "Health", "Office", "Pet",
          ]);
          setLoading(false);
        }
      });
    return () => { cancelled = true; };
  }, [api]);

  if (loading) {
    return (
      <div className="amazon-loading">
        <div className="amazon-spinner" />
        <p>Loading categories...</p>
      </div>
    );
  }

  return (
    <div className="categories-page">
      <h1>Shop by Category</h1>
      <p className="categories-page__subtitle">Browse our full selection of departments</p>

      <div className="categories-grid">
        {categories.map((cat, index) => (
          <Link
            key={cat}
            to={preserveQueryParams(`/search?q=&category=${encodeURIComponent(cat)}`, location.search)}
            className="categories-grid__card"
          >
            <div
              className="categories-grid__icon"
              style={{ backgroundColor: CATEGORY_COLORS[index % CATEGORY_COLORS.length] }}
            >
              {CATEGORY_ICONS[cat] || cat.charAt(0).toUpperCase()}
            </div>
            <span className="categories-grid__name">{cat}</span>
          </Link>
        ))}
      </div>
    </div>
  );
}
