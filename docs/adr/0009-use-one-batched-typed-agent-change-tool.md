# Use one batched typed agent change tool

The V0.2 agent reads current scheduling decisions through a read-only tool and prepares all mutations through one `propose_changes` tool accepting a list of discriminated `WorkspaceChange` values. Typed add, update, and remove variants cover the closed policy and objective catalogue; the whole prospective workspace is validated together and returned as a domain-language confirmation diff, while the tool itself never commits. This avoids partial multi-tool mutation, generic parameter dictionaries, and model-controlled persistence.
