import ibm_db_dbi
import ibm_db
import logging
from plugins.applications.db2 import feature
from utils.crawler_exceptions import CrawlError


logger = logging.getLogger('crawlutils')


def retrieve_metrics(host='localhost',
                     user='db2inst1', password='db2inst1-pwd',
                     db='sample'):

    sql_list = ["SELECT db_size FROM systools.stmg_dbsize_info",
                "SELECT db_capacity FROM systools.stmg_dbsize_info",
                "select service_level concat ' FP'"
                "concat fixpack_num from sysibmadm.env_inst_info",
                "select inst_name from sysibmadm.env_inst_info",
                "Select PRODUCT_NAME from sysibmadm.snapdbm",
                "Select DB_NAME from sysibmadm.snapdb",
                "Select SERVICE_LEVEL from sysibmadm.snapdbm",
                "Select REM_CONS_IN + LOCAL_CONS  from sysibmadm.snapdbm",
                "Select sum(POOL_CUR_SIZE) from sysibmadm.SNAPDBM_MEMORY_POOL",
                "Select TOTAL_CONS from sysibmadm.snapdb",
                "Select TOTAL_LOG_USED *1. / "
                "TOTAL_LOG_AVAILABLE * 100. from sysibmadm.snapdb",
                "Select NUM_INDOUBT_TRANS from sysibmadm.snapdb",
                "Select X_LOCK_ESCALS from sysibmadm.snapdb",
                "Select LOCK_ESCALS from sysibmadm.snapdb",
                "Select LOCK_TIMEOUTS from sysibmadm.snapdb",
                "Select DEADLOCKS from sysibmadm.snapdb",
                "Select LAST_BACKUP from sysibmadm.snapdb",
                "Select DB_STATUS from sysibmadm.snapdb",
                "select DB2_STATUS from sysibmadm.snapdbm",
                "select case POOL_INDEX_L_READS when  0 then 1 else "
                "(POOL_INDEX_L_READS * 1.  - POOL_INDEX_P_READS * 1.) / "
                "POOL_INDEX_L_READS end * 100.  from sysibmadm.snapdb",
                "select case POOL_DATA_L_READS when 0 then 1 else "
                "(POOL_DATA_L_READS * 1.  - POOL_DATA_P_READS * 1.) / "
                "POOL_DATA_L_READS end *100. from sysibmadm.snapdb",
                "select case TOTAL_SORTS when 0 then 0 else SORT_OVERFLOWS "
                "*1. / TOTAL_SORTS *1. end * 100. from sysibmadm.snapdb",
                "select COALESCE(AGENTS_WAITING_TOP,0) from sysibmadm.snapdbm",
                "Select ROWS_UPDATED from sysibmadm.snapdb",
                "Select ROWS_INSERTED from sysibmadm.snapdb",
                "Select ROWS_SELECTED from sysibmadm.snapdb",
                "Select ROWS_DELETED from sysibmadm.snapdb",
                "Select SELECT_SQL_STMTS from sysibmadm.snapdb",
                "Select STATIC_SQL_STMTS from sysibmadm.snapdb",
                "Select DYNAMIC_SQL_STMTS  from sysibmadm.snapdb",
                "Select ROLLBACK_SQL_STMTS  from sysibmadm.snapdb",
                "Select COMMIT_SQL_STMTS from sysibmadm.snapdb",
                "select case POOL_TEMP_INDEX_L_READS when 0 then 1 "
                "else (POOL_TEMP_INDEX_L_READS * 1. - "
                "POOL_TEMP_INDEX_P_READS * 1.) / POOL_TEMP_INDEX_L_READS end "
                "* 100 from sysibmadm.snapdb",
                "select case POOL_TEMP_DATA_L_READS when 0 then 1 else "
                "(POOL_TEMP_DATA_L_READS * 1. - POOL_TEMP_DATA_P_READS * 1.) /"
                "  POOL_TEMP_DATA_L_READS end * 100. from sysibmadm.snapdb"
                ]

    sql_stats = ["dbSize",
                 "dbCapacity",
                 "dbVersion",
                 "instanceName",
                 "productName",
                 "dbName",
                 "serviceLevel",
                 "instanceConn",
                 "instanceUsedMem",
                 "dbConn",
                 "usedLog",
                 "transcationInDoubt",
                 "xlocksEscalation",
                 "locksEscalation",
                 "locksTimeOut",
                 "deadLock",
                 "lastBackupTime",
                 "dbStatus",
                 "instanceStatus",
                 "bpIndexHitRatio",
                 "bpDatahitRatio",
                 "sortsInOverflow",
                 "agetnsWait",
                 "updateRows",
                 "insertRows",
                 "selectedRows",
                 "deleteRows",
                 "selects",
                 "selectSQLs",
                 "dynamicSQLs",
                 "rollbacks",
                 "commits",
                 "bpTempIndexHitRatio",
                 "bpTempDataHitRatio"
                 ]

    sql_stats_list = {}

    try:
        ibm_db_conn = ibm_db.connect("DATABASE=" + db +
                                     ";HOSTNAME=" + host +
                                     ";UID=" + user +
                                     ";PWD="+password+";", "", "")
        conn = ibm_db_dbi.Connection(ibm_db_conn)
    except:
        raise CrawlError("cannot connect to database,"
                         " db: %s, host: %s ", db, host)

    c = conn.cursor()

    i = 0
    for sql in sql_list:
        try:
            c.execute(sql)
        except:
            raise CrawlError("cannot execute sql %s", sql)
        sql_stats_list[sql_stats[i]] = str(c.fetchone()[0])
        i += 1

    db2_attributes = feature.DB2Feature(
        sql_stats_list["dbCapacity"],
        sql_stats_list["dbVersion"],
        sql_stats_list["instanceName"],
        sql_stats_list["productName"],
        sql_stats_list["dbName"],
        sql_stats_list["serviceLevel"],
        sql_stats_list["instanceConn"],
        sql_stats_list["instanceUsedMem"],
        sql_stats_list["dbConn"],
        sql_stats_list["usedLog"],
        sql_stats_list["transcationInDoubt"],
        sql_stats_list["xlocksEscalation"],
        sql_stats_list["locksEscalation"],
        sql_stats_list["locksTimeOut"],
        sql_stats_list["deadLock"],
        sql_stats_list["lastBackupTime"],
        sql_stats_list["dbStatus"],
        sql_stats_list["instanceStatus"],
        sql_stats_list["bpIndexHitRatio"],
        sql_stats_list["bpDatahitRatio"],
        sql_stats_list["sortsInOverflow"],
        sql_stats_list["agetnsWait"],
        sql_stats_list["updateRows"],
        sql_stats_list["insertRows"],
        sql_stats_list["selectedRows"],
        sql_stats_list["deleteRows"],
        sql_stats_list["selects"],
        sql_stats_list["selectSQLs"],
        sql_stats_list["dynamicSQLs"],
        sql_stats_list["rollbacks"],
        sql_stats_list["commits"],
        sql_stats_list["bpTempIndexHitRatio"],
        sql_stats_list["bpTempDataHitRatio"]
    )
    return db2_attributes
