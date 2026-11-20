"""honest-persist: schema-first, pure-function persistence. Rebuilt from the declaration.

Schema is data, a migration is a pure diff of what-you-have against what-you-want, and a query is data
run at one I/O boundary. honest-persist drives sqlite, postgresql and turso behind one declaration, holds
no session and no identity map, and hands the caller data, never a connection. Ported from
declaro-persistum; the conflict retry is a driven generator (honest-persist spec 7.7).
"""

from honest_persist.engines import (
    capability_of,
    engine_of,
    how_to_compare,
    how_to_inspect,
    how_to_migrate,
    how_to_retry,
    how_to_spell,
    how_to_write,
    refuse_unusable_settings,
    what_an_operation_carries,
)
from honest_persist.retry import (
    budget_spent,
    crew_size,
    next_in_order,
    next_wait,
    permitted_connections,
    progress_line,
    receipt_for,
    refusal_reaches_caller,
    replicates,
    retry_schedule,
    what_to_do_after_a_refresh,
    worth_retrying,
    writer_waiting,
)
from honest_persist.schema import (
    difference,
    field,
    migration_needed,
    name_what_destroys,
    name_what_is_ambiguous,
    order_operations,
    refuse_owned_names,
    refuse_undeclared_loss,
    schema_from_declared,
)
from honest_persist.query import (
    answer_from_receipt,
    answer_from_rows,
    asked_from_written,
    compile_statement,
    condition_from_narrowing,
    declaration_from_asked,
    grammar_of,
    join_between,
    methods_of,
    refuse_some_columns_as_an_object,
    refuse_undeclared_columns,
    travels_together,
)
from honest_persist.spelling import mechanism_for, spell_operation, spell_view
from honest_persist.refresh import refreshes_from_declared
from honest_persist.io import (
    channel_pull,
    channel_push,
    clock_read,
    copy_on_disk,
    crew_run_write,
    log_write,
    query_run_statement,
    query_run_together,
    schema_inspect,
    schema_read_declared,
    session_close_connection,
    session_open_channel,
    session_open_connection,
    session_open_writer,
)
from honest_persist.crew import (
    crew_deposit,
    crew_make,
    crew_post_receipt,
    crew_release_ticket,
    crew_start,
    crew_stop,
    crew_wait_for_work,
    lifecycle_install_handler,
    lifecycle_register,
)
from honest_persist.orchestrators import (
    lifecycle_catch_up,
    lifecycle_shut_down,
    migration_compare,
    query_answer,
    schema_read_live,
    schema_say_declared,
    schema_say_refreshes,
    session_connect,
)
from honest_persist.doors import (
    lifecycle_stop,
    lifecycle_turn,
    migration_plan,
    query_ask,
    schema_declared,
    schema_live,
    session_open,
    view_refreshes,
)
from honest_persist.query_layer import (
    delete,
    execute,
    execute_many,
    execute_one,
    execute_scalar,
    insert,
    raw,
    select,
    transaction,
    update,
)
from honest_persist.types import (
    ENGINES,
    FAULT_CATEGORIES,
    Fault,
    fault,
    is_fault,
    is_no_match,
    no_match,
    refused,
)

__all__ = [
    # input I/O doors
    "session_open", "query_ask", "lifecycle_stop", "clock_read", "copy_on_disk", "lifecycle_turn",
    "migration_plan", "schema_live", "schema_declared", "view_refreshes",
    # orchestrators
    "session_connect", "query_answer", "migration_compare", "schema_read_live", "schema_say_declared",
    "schema_say_refreshes", "lifecycle_shut_down", "lifecycle_catch_up",
    # output I/O
    "session_open_connection", "query_run_statement", "channel_pull", "channel_push",
    "session_close_connection", "session_open_writer", "session_open_channel", "crew_make",
    "crew_start", "crew_stop", "query_run_together", "crew_run_write", "crew_deposit",
    "lifecycle_install_handler", "crew_release_ticket", "crew_post_receipt", "crew_wait_for_work",
    "schema_read_declared", "schema_inspect", "log_write",
    # pure core
    "engine_of", "refuse_unusable_settings", "crew_size", "permitted_connections", "compile_statement",
    "refuse_undeclared_columns", "refuse_some_columns_as_an_object", "travels_together",
    "answer_from_receipt", "answer_from_rows", "condition_from_narrowing", "methods_of",
    "asked_from_written", "declaration_from_asked", "grammar_of", "replicates", "next_wait",
    "progress_line", "writer_waiting", "next_in_order", "worth_retrying", "budget_spent", "how_to_retry",
    "retry_schedule", "refusal_reaches_caller", "lifecycle_register", "receipt_for",
    # schema half
    "field", "refuse_owned_names", "schema_from_declared", "refuse_undeclared_loss", "migration_needed",
    "difference", "name_what_is_ambiguous", "order_operations", "name_what_destroys", "capability_of",
    "how_to_write", "how_to_migrate", "how_to_inspect", "how_to_spell", "what_an_operation_carries",
    "how_to_compare", "spell_operation",
    # across models, declared view
    "join_between", "spell_view", "mechanism_for", "refreshes_from_declared", "what_to_do_after_a_refresh",
    # query layer (spec 7)
    "select", "insert", "update", "delete", "raw",
    "execute", "execute_one", "execute_scalar", "execute_many", "transaction",
    # infrastructure
    "Fault", "fault", "is_fault", "refused", "no_match", "is_no_match", "ENGINES", "FAULT_CATEGORIES",
]
