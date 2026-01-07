console.log('Removing items');

ServerEvents.recipes(event => {
    event.remove({ output: 'computercraft:turtle_advanced' })
    event.remove({ output: 'computercraft:turtle_normal' })
})