# OpenRouter privacy and retention

Research date: 2026-07-30  
Scope: disclosures and request controls for MedShift's optional OpenRouter-backed chat. Sources are OpenRouter's official documentation, Privacy Policy, and Terms of Service.

## Findings

### Data leaves the local application

Every chat request sent through OpenRouter is processed by OpenRouter and its contents are transmitted to the selected model provider—or to a provider selected by automatic routing. Provider practices vary and can include retention, evaluation, model improvement, or training. OpenRouter's default routing load-balances among providers and permits fallback providers, so the downstream processor may vary between requests and a failed request may be attempted with another provider. [Privacy Policy: Model Provider Data Practices](https://openrouter.ai/privacy/), [Provider Routing](https://openrouter.ai/docs/guides/routing/provider-selection), [Model Fallbacks](https://openrouter.ai/docs/guides/routing/model-fallbacks)

The product must therefore not claim that chat remains local. Its consent disclosure should identify the complete application payload sent to OpenRouter, say that the payload is also sent to one or more downstream model providers for inference, and warn users not to type patient, employee, or other identifying information into chat.

### What OpenRouter retains

For ordinary inference, OpenRouter says prompt and response content is not stored unless the account opts into either of two independent settings:

- **Private Input & Output Logging**, which stores full prompts and completions for review. It is off by default. When enabled, content is retained for at least three months and possibly longer at OpenRouter's discretion unless the account owner requests deletion.
- **OpenRouter Use of Inputs/Outputs**, which permits OpenRouter to use prompt and completion data to improve its product in exchange for a discount. It is also off by default.

OpenRouter nevertheless stores request metadata such as timestamps, model, token counts, latency, provider, and cost. Its public documentation gives no fixed retention period for this metadata; the Privacy Policy says personal data is retained as reasonably necessary for business, legal, regulatory, and compliance obligations. [Data Collection](https://openrouter.ai/docs/guides/privacy/data-collection), [Input & Output Logging](https://openrouter.ai/docs/guides/features/input-output-logging), [FAQ: Privacy and Data Logging](https://openrouter.ai/docs/faq), [Privacy Policy: Personal Data Retention](https://openrouter.ai/privacy/)

OpenRouter also samples a small number of prompts for anonymous categorization used in reporting and rankings. When use of inputs/outputs is not enabled, OpenRouter says the categorizer uses a zero-retention model, does not associate the category with the account, and does not retain the input after categorization. [Data Collection](https://openrouter.ai/docs/guides/privacy/data-collection), [Terms §6.5](https://openrouter.ai/terms)

Both content-retention settings are documented as account/workspace settings; the public API documentation does not describe a per-request switch that forces them off. A local app using a user-supplied API key therefore should not promise that OpenRouter will never store content merely because the app itself does no logging. That depends on the user's OpenRouter settings. If prompt logging is enabled, OpenRouter's Terms grant it broad, perpetual rights for commercial and business purposes, including anonymized distribution. [Input & Output Logging](https://openrouter.ai/docs/guides/features/input-output-logging), [Terms §6.2](https://openrouter.ai/terms)

### Downstream provider controls

Provider-side policy is distinct from OpenRouter's own content settings:

- `provider.data_collection: "deny"` restricts routing to endpoints OpenRouter classifies as not collecting user data. The default is `"allow"`, which permits endpoints that store data non-transiently and may train on it.
- `provider.zdr: true` restricts inference routing to endpoints classified as **Zero Data Retention**. OpenRouter defines ZDR as the provider not storing the request for any period and says a ZDR provider therefore cannot train on it.
- A provider allowlist (`provider.only`) and `allow_fallbacks: false` can further make the intended downstream destination predictable, at the cost of availability.

For MedShift's privacy-preserving default, each request should set both `data_collection: "deny"` and `zdr: true`. This may reduce the available models/endpoints; if no compatible endpoint is available, chat should fail closed rather than retry without those restrictions. [Provider Routing: data-policy filtering and ZDR](https://openrouter.ai/docs/guides/routing/provider-selection), [Zero Data Retention](https://openrouter.ai/docs/guides/features/zdr)

### ZDR limitations

ZDR is not a blanket “nothing is logged” guarantee:

- It controls downstream provider routing for inference, not OpenRouter's request metadata, the user's OpenRouter content-logging settings, or third-party plugins/tools.
- OpenRouter considers provider-side in-memory prompt caching compatible with ZDR.
- Policies are endpoint-specific and can differ from a provider's general policy. OpenRouter maintains the classifications and assumes retention and training when a policy is unclear, but its routing page calls its third-party policy labels “our best knowledge” rather than definitive.
- Provider terms and available ZDR endpoints can change. OpenRouter's Terms say model terms may be incorrect, missing, or outdated and place responsibility on the customer to review them.
- OpenRouter's Privacy Policy says it cannot guarantee transmission security and that data may be transferred to the United States or other countries outside the EEA/UK. EU in-region routing is a separate enterprise-only feature.

[Zero Data Retention](https://openrouter.ai/docs/guides/features/zdr), [Provider Logging](https://openrouter.ai/docs/guides/privacy/provider-logging/), [Provider Routing](https://openrouter.ai/docs/guides/routing/provider-selection), [Terms §§5–6](https://openrouter.ai/terms), [Privacy Policy: Security and Transfers](https://openrouter.ai/privacy/)

## Deployment-safe recommendation

Before deployment, MedShift should complete privacy/legal review and decide on
an enforceable provider policy. A privacy-preserving configuration would send
both `data_collection: "deny"` and `zdr: true`, optionally combine those with a
provider allowlist and disabled fallbacks, and fail closed when no compatible
endpoint is available.

That configuration would support a disclosure such as:

> Chat is optional and sends your message, recent chat history, active scheduling policies and objectives, fixed Shift Type definitions, and aggregate scenario statistics to OpenRouter. OpenRouter sends this data to a downstream model provider to generate a response. MedShift does not send employee names, IDs, individual balances or hour ceilings, fixed assignments, employee preferences, department names, or the workspace file unless you type such information into chat yourself.
>
> MedShift requests only endpoints that OpenRouter currently classifies as zero-data-retention and as not collecting prompts. OpenRouter still records request metadata, and your OpenRouter account settings may independently enable prompt/response storage. Provider classifications and terms can change, so zero retention cannot be guaranteed absolutely. Do not enter patient, employee, or other identifying information.

The enablement screen should link to the current [OpenRouter Privacy Policy](https://openrouter.ai/privacy/), [OpenRouter data-collection documentation](https://openrouter.ai/docs/guides/privacy/data-collection), and [OpenRouter ZDR documentation](https://openrouter.ai/docs/guides/features/zdr). The application should remain fully usable without enabling Chat.

## Accepted V0.2 prototype decision

V0.2 deliberately uses standard OpenRouter routing and therefore must not use
the strict-routing disclosure above. Its consent text must instead state that
OpenRouter and downstream providers may retain or use submitted content, and
must tell users not to enter patient, Employee, or other identifying
information. Strict provider routing and privacy/legal review remain mandatory
questions before deployment. See
[`0010-defer-strict-provider-privacy-controls-until-deployment.md`](../adr/0010-defer-strict-provider-privacy-controls-until-deployment.md).
