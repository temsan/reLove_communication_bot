// Базовая конфигурация ESLint для поддержки HTML и встроенного JavaScript
// Базовая конфигурация ESLint для CommonJS
module.exports = [
  {
    files: ["**/*.js", "**/*.html"],
    languageOptions: {
      ecmaVersion: 2022,
      sourceType: "module",
    },
    rules: {
      semi: ["error", "always"],
      quotes: ["error", "double"],
      "no-unused-vars": "warn",
      "no-console": "off"
    },
  },
];
