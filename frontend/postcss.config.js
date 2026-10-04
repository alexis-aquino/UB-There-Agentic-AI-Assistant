import postcssNesting from 'postcss-nesting';

// The design files (src/designs/*.css) are written with CSS nesting. This flattens it for
// every browser, in dev and build alike: phone browsers from before ~2024 only partly
// support nesting and silently drop whole designs they can't parse.
export default {
  plugins: [postcssNesting()],
};
