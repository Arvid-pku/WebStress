/** @type {import('next').NextConfig} */
const nextConfig = {
  output: "export",
  transpilePackages: ["@webstress/shared", "@webstress/gmail"],
  images: { unoptimized: true },
};

module.exports = nextConfig;
