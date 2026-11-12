-- Run only in an isolated --test-scenario session, never in a normal save.
script.on_init(function()
  for _, name in ipairs({"space-age", "elevated-rails", "quality", "recycler"}) do
    assert(script.active_mods[name], "Missing expansion mod: " .. name)
  end
  for _, name in ipairs({"nauvis", "vulcanus", "fulgora", "gleba", "aquilo"}) do
    local surface = assert(game.planets[name], "Missing planet: " .. name).create_surface()
    local settings = surface.map_gen_settings
    settings.width = 64
    settings.height = 64
    settings.seed = 12345
    surface.map_gen_settings = settings
    surface.request_to_generate_chunks({0, 0}, 1)
    surface.force_generate_chunk_requests()
    assert(surface.is_chunk_generated({0, 0}), "Planet generation failed: " .. name)
    log("FACTORIO_PORT_EXPANSION_TEST: generated " .. name)
  end
  for _, name in ipairs({"recycler", "elevated-straight-rail", "foundry", "biochamber", "electromagnetic-plant", "cryogenic-plant", "asteroid-collector"}) do
    assert(prototypes.entity[name], "Missing expansion entity: " .. name)
  end
  local chest = game.surfaces.nauvis.create_entity{name="steel-chest", position={0, 0}, force="player", quality="legendary"}
  assert(chest and chest.quality.name == "legendary", "Legendary quality creation failed")
  storage.platform = assert(game.forces.player.create_space_platform{
    name="port-validation", planet="nauvis", starter_pack="space-platform-starter-pack"
  }, "Platform creation failed")
  assert(storage.platform.apply_starter_pack(), "Platform hub creation failed")
end)

script.on_nth_tick(120, function()
  if game.tick < 120 then return end
  assert(storage.platform.valid and storage.platform.hub.valid, "Platform was lost during simulation")
  log("FACTORIO_PORT_EXPANSION_TEST: PASS")
  script.finish_test(true)
end)
