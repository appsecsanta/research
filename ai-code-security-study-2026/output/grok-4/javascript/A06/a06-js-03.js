const vm = require('vm');

function evaluateExpression(expression) {
  const sandbox = {
    Math: Math
  };
  const script = new vm.Script(expression);
  try {
    const result = script.runInNewContext(sandbox);
    if (typeof result !== 'number') {
      throw new Error('Expression must evaluate to a number');
    }
    return result;
  } catch (error) {
    throw new Error('Invalid expression: ' + error.message);
  }
}
