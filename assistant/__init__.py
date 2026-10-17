"""The portal assistant's toolbox (docs/ASSISTANT.md).

Every action the assistant can take is a plain, tested function in this package. A model,
Grok or Claude, chooses which one to call and phrases the answer; the function does the exact
work. Read tools only read. Propose tools only record a change request, which a person
approves on the dashboard before the scan machine carries it out.
"""
