console.log('Hiding items in JEI, pre-event');

JEIEvents.hideItems(event => {
    event.hide('computercraft:turtle_normal')
    event.hide('computercraft:turtle_advanced')
})