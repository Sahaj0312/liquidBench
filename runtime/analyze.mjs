import { toLiquidHtmlAST, walk, LiquidHTMLASTParsingError } from '@shopify/liquid-html-parser';
import { readFileSync } from 'node:fs';

const { source } = JSON.parse(readFileSync(0, 'utf8'));
try {
  const ast = toLiquidHtmlAST(source, { mode: 'strict', allowUnclosedDocumentNode: false });
  const schemas = [];
  walk(ast, (node, parent) => {
    if (node.type === 'LiquidRawTag' && node.name === 'schema') {
      schemas.push({
        body: node.body.value, top_level: parent === ast,
        block: source.slice(node.position.start, node.position.end),
        start: node.position.start, end: node.position.end,
      });
    }
  });
  // Metadata extraction only. This does not implement Shopify section rendering.
  const bodySource = schemas.length === 1 && schemas[0].top_level
    ? source.slice(0, schemas[0].start) + source.slice(schemas[0].end)
    : schemas.length === 0 ? source : null;
  const compactAST = JSON.parse(JSON.stringify(ast, (key, value) =>
    ['source', '_source', 'position', 'rawSource'].includes(key) || key.endsWith('Position')
      ? undefined : value));
  const output = JSON.stringify({ ok: true, ast: compactAST, schemas, body_source: bodySource });
  if (output.length > 512000) throw new RangeError('Analysis exceeds size limit');
  console.log(output);
} catch (error) {
  if (!(error instanceof LiquidHTMLASTParsingError) && !(error instanceof RangeError)) throw error;
  console.log(JSON.stringify({ ok: false, error: error.message.slice(0, 1000) }));
}
