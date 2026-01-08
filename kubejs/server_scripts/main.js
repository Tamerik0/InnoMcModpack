ServerEvents.recipes(event => {
    event.remove({ output: 'computercraft:computer_normal' })
    event.recipes.create.mechanical_crafting('computercraft:computer_normal', [
    ' PPPPP ',
    'PCWNWCP',
    'PWBLBWP',
    'PNLTLNP',
    'PWBLBWP',
    'PCWNWCP',
    ' PPPPP '
    ], {
        P: 'create:iron_sheet',
        C: 'create_connected:control_chip',
        W: 'tfmg:copper_wire',
        N: 'computercraft:cable',
        B: 'tfmg:circuit_board',
        L: 'integrateddynamics:logic_director',
        T: 'integratedscripting:part_terminal_scripting'
    })
    event.remove({ output: 'computercraft:computer_advanced' })
    event.recipes.create.sequenced_assembly([
        Item.of('computercraft:computer_advanced'),
     ], 'computercraft:computer_normal', [ 
        event.recipes.createDeploying('computercraft:computer_normal', ['computercraft:computer_normal', 'tfmg:circuit_board']),
        event.recipes.createDeploying('computercraft:computer_normal', ['computercraft:computer_normal', 'integrateddynamics:cable']),
        event.recipes.createDeploying('computercraft:computer_normal', ['computercraft:computer_normal', 'minecraft:gold_nugget'])
     ]).transitionalItem('computercraft:computer_normal') 
       .loops(3) 
    event.remove({ output: 'computercraft:cable' })
    event.shaped('10x computercraft:cable', [
         'WAW',
         'ARA',
         'WAW'
     ], {
         A: 'create:andesite_alloy',
         W: 'tfmg:copper_wire',
         R: 'minecraft:redstone'
    })
    event.remove({ output: 'integrateddynamics:cable' })
    event.shaped('3x integrateddynamics:cable', [
         'MMM',
         'CCC',
         'MMM'
     ], {
         M: 'integrateddynamics:crystalized_menril_chunk',
         C: 'computercraft:cable'
     })
    event.remove({ output: 'create:deployer' })
    event.shaped('create:deployer', [
         'CRC',
         'TGT',
         ' H '
    ], {
         G: 'create_connected:parallel_gearbox',
         H: 'create:brass_hand',
         T: 'create:electron_tube',
         R: 'minecraft:redstone',
         C: 'create:cogwheel'
    })
    event.remove({ output: 'create:mechanical_crafter' })
    event.shaped('create:mechanical_crafter', [
         'WCW',
         'TGT',
         'WPW'
    ], {
         P: 'create:precision_mechanism',
         C: 'create_connected:control_chip',
         T: 'create:electron_tube',
         G: 'create:brass_casing',
         W: 'create:cogwheel'
    })
    event.remove({output: 'integrateddynamics:proto_chorus'})
    event.recipes.create.mixing('integrateddynamics:proto_chorus', [
        'integrateddynamics:menril_berries',
        'minecraft:ender_pearl',
        'mna:resonating_dust'
    ]).heated()
    event.remove({ id: /^integrateddynamics:squeezer\/ore/ })
    event.remove({ id: /^integrateddynamics:mechanical_squeezer\/ore/ })
    event.remove({output: 'vstuff:phys_grabber'})
    event.recipes.create.mechanical_crafting('vstuff:phys_grabber', [
    '   SSS',
    'AEWMWI',
    'BBBII '
    ], {
        W: 'vs_clockwork:wanderlite_matrix',
        S: 'create:brass_sheet',
        B: 'create:brass_ingot',
        A: 'create:andesite_alloy',
        I: 'tfmg:cast_iron_sheet',
        E: 'vstuff:energy_core',
        M: 'mna:purified_vinteum_coated_iron'
    })
    event.remove({output: 'vs_clockwork:gravitron'})
    event.recipes.create.mechanical_crafting('vs_clockwork:gravitron', [
    'ELD',
    'RGR',
    'DBE'
    ], {
        G: 'vstuff:phys_grabber',
        L: 'fdbosses:lightning_core',
        B: 'tfmg:circuit_board',
        D: 'integrateddynamics:logic_director',
        E: 'vstuff:energy_core',
        R: 'apotheosis:rare_material'
    })
    event.recipes.create.mechanical_crafting('the_vmod:physgun', [
    'ELD',
    'RGR',
    'DBE'
    ], {
        G: 'vs_clockwork:gravitron',
        L: 'fdbosses:fire_and_ice_core',
        B: 'tfmg:circuit_board',
        D: 'minecraft:nether_star',
        E: 'mna:superheated_purified_vinteum_ingot',
        R: 'apotheosis:epic_material'
    })
    event.shapeless('vs_clockwork:creative_gravitron', ['the_vmod:physgun', 'computercraft:pocket_computer_normal'])
    event.shapeless('the_vmod:toolgun', ['vs_clockwork:creative_gravitron', 'computercraft:pocket_computer_advanced', 'apotheosis:mythic_material'])
    event.remove({ output: 'computercraft:pocket_computer_normal' })
    event.remove({ output: 'computercraft:pocket_computer_advanced' })
    event.shapeless('computercraft:pocket_computer_normal', ['computercraft:computer_normal'])
    event.shapeless('computercraft:pocket_computer_advanced', ['computercraft:computer_advanced'])
    event.shapeless('computercraft:computer_normal', ['computercraft:pocket_computer_normal'])
    event.shapeless('computercraft:computer_advanced', ['computercraft:pocket_computer_advanced'])
 })