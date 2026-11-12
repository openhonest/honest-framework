Feature: honest-page — Python supplement
  One scenario per declared function in honest-page.hd, titled by the function name so proof_run
  maps each scenario to its def. The Then lines read for a human; the executable oracle is the
  value_case entries in conformance/suite.json, with the unpinnable outputs (the app handle, the
  assembly plan, the registrations) carried by laws in conformance/laws_hp.py instead. Counted
  toward the module's function points alongside any neutral scenarios in specs/features.

  # The request path — a typed request becomes a rendered page, pure core first.

  Scenario: extract_tokens merges the three token sources by specificity
    Given path parameters, query parameters, and the _state the page collected
    When extract_tokens merges them
    Then it returns one manifest in which _state wins over a query parameter, which wins over a path parameter

  Scenario: search_chain filters the rows the manifest asks for
    Given a manifest carrying a search term
    When search_chain runs
    Then it returns only the rows that contain the term

  Scenario: page_context builds the server-side context around a title
    Given a page title
    When page_context builds the context
    Then it returns the section 6 variables, the given title among the declared defaults

  Scenario: surface_slot resolves a surface id against the declared surfaces
    Given a surface id
    When surface_slot resolves it
    Then it returns the slot that surface's markup lands in, or nothing when the id is not a declared surface

  Scenario: build_manifest classifies a request into one manifest
    Given the path parameters, query parameters, and _state of a request
    When build_manifest runs
    Then it invokes extract_tokens and returns the classified manifest

  Scenario: run_search runs the search chain over a manifest
    Given a classified manifest
    When run_search runs
    Then it invokes search_chain and returns the matching rows

  Scenario: build_home builds the home page context
    Given the home page title
    When build_home runs
    Then it invokes page_context and returns the home context

  Scenario: intake classifies every request before it reaches a handler
    Given a request and the next handler in the chain
    When intake runs
    Then it hands the request to build_manifest, places the manifest on the request, and calls the next handler

  Scenario: index renders the home page
    Given a request for the site root
    When index runs
    Then it hands the title to build_home and returns the rendered full page

  Scenario: search renders the search fragment
    Given a request carrying a search manifest
    When search runs
    Then it hands the manifest to run_search and returns the rendered fragment, which does not extend the base page

  # The composition root — the app factory FastAPI runs (spec section 10.4).

  Scenario: read_bundle pulls the bundled template and static directories
    Given the package as shipped
    When read_bundle runs
    Then it returns the template and static directory paths the factory mounts

  Scenario: route_table declares the route map as data
    Given no input
    When route_table runs
    Then it returns one entry per route, each pairing a method and path with the chain that path runs

  Scenario: assembly lays out what the factory mounts, in order
    Given the bundle and the route table
    When assembly runs
    Then it returns the plan: static, templates, intake ahead of every route, one handler per route-map entry

  Scenario: install creates the application and applies the plan
    Given an assembly plan
    When install runs
    Then it creates the application object, mounts static and templates, installs intake, registers each route, and returns the application

  Scenario: build_app assembles the application from its parts
    Given no input
    When build_app runs
    Then it invokes read_bundle, route_table, assembly, and install, and returns the application

  Scenario: create_app is the composition root the host calls
    Given a host that imports the factory
    When create_app runs
    Then it hands off to build_app and returns the application the ASGI server runs

  # The SSE extension hook — a custom module attaches its own stream (spec section 4.5).

  Scenario: register_source registers a source on the stream
    Given a resolved slot, an event type, and a source
    When register_source runs
    Then it registers the source against that slot on the alert stream

  Scenario: attach resolves the surface and registers the source
    Given a surface id, an event type, and a source
    When attach runs
    Then it invokes surface_slot to resolve the surface and register_source to register the source

  Scenario: attach_stream lets a custom module hook into the page SSE
    Given a module registering its own source against one declared surface
    When attach_stream runs
    Then it hands off to attach and registers the source without honest-page naming that module
