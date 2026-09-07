/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  eslint: {
    // The dashboard is linted with `npm run lint` when desired; builds
    // stay green even without an eslint config installed.
    ignoreDuringBuilds: true,
  },
  typescript: {
    // Type errors SHOULD fail the build — this is a typed codebase.
    ignoreBuildErrors: false,
  },
  images: {
    // Discord CDN avatars/icons are loaded with plain <img> tags; no
    // next/image remote optimization needed.
    unoptimized: true,
  },
};

module.exports = nextConfig;
