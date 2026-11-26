# catalog

## Catalog

The catalog lists available items.

A second paragraph explains the order.

## Types

| Type | Field | Type |
| --- | --- | --- |
| Item | title | str |

## Sets

| Set | Member |
| --- | --- |
| modes | plain |

## Vocabularies

| Vocabulary | Sets |
| --- | --- |
| Mode | modes |

## Dispatches

| Dispatch | Key | Target |
| --- | --- | --- |
| by_mode | plain | prepare |

## Chains

1. main: receive -> coordinate
2. preview: prepare

## Routes

1. GET /catalog receive
2. POST /catalog receive

## Entries

1. import catalog receive
2. call:preview receive
