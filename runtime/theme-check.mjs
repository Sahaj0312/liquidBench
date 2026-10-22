import { check } from '@shopify/theme-check-node';
// The workspace cannot supply configuration; its path is explicitly overridden.
const offenses = await check('/workspace', '/opt/liquidbench/theme-check.yml');
console.log(JSON.stringify(offenses));
