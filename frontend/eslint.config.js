import vue from 'eslint-plugin-vue'
import ts from 'typescript-eslint'
export default ts.config(
  {ignores:['src/api/schema.d.ts']},
  ...ts.configs.recommended,
  ...vue.configs['flat/recommended'],
  {files:['**/*.vue'],languageOptions:{parserOptions:{parser:ts.parser}},rules:{'vue/multi-word-component-names':'off','vue/max-attributes-per-line':'off','vue/html-self-closing':'off','vue/singleline-html-element-content-newline':'off','vue/html-indent':'off','vue/first-attribute-linebreak':'off','vue/html-closing-bracket-newline':'off','vue/multiline-html-element-content-newline':'off'}}
)
