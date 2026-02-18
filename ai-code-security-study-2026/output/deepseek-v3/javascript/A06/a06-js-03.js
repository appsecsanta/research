function evaluateExpression(expression) {
    try {
        // Ensure the expression is safe to evaluate
        if (/^[0-9+\-*\/\s().Math,sqrt]*$/.test(expression)) {
            return new Function(`return ${expression}`)();
        } else {
            throw new Error('Invalid expression');
        }
    } catch (error) {
        console.error('Error evaluating expression:', error);
        return NaN;
    }
}
