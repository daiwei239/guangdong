# app/schemas/topology_schema.py

# 定义系统允许的所有合法异构图边关系 (Source_Type, Relation_Type, Target_Type)
BASE_EDGE_RELATIONS = {
    ## 同一台机器之间的连接
    #计算与内存之间的挂载关系
    ("CPU","SHARED_MEMORY","MEMORY"),
    ("GPU","SHARED_MEMORY","MEMORY"),
    
    #同宿主机不同资源之间的连接
    ("CPU","SAME_HOST","GPU"),
    ("CPU","SAME_HOST","FPGA"),
    ("CPU","SAME_HOST","NIC"),
    ("CPU","SAME_HOST","STORAGE"),
    ("GPU","SAME_HOST","STORAGE"),
    ("STORAGE","SAME_HOST",'NIC'),

    #绕过cpu的连接关系
    ("GPU","SAME_HOST","NIC"),
    ("FPGA", "SAME_HOST", "NIC"),

    #加速卡之间的连接
    ("CPU", "LOW_LATENCY_LINK", "CPU"),
    ("GPU","LOW_LATENCY_LINK","GPU"),
    ("FPGA","LOW_LATENCY_LINK","FPGA"),
    
    ## 外部连接
    #不同机器之间的连接,跨机器通信的实现
    ("NIC","CONNECTED_TO","SWITCH"),
    ("SWITCH","CONNECTED_TO","SWITCH"),

    ("SWITCH","SAME_RACK","SWITCH"),
    ("CPU","SAME_RACK","CPU"),

    ("GPU","COMPETES_BANDWIDTH","GPU"),
    ("GPU","COMPETES_BANDWIDTH","NIC"),
    ("STORAGE", "COMPETES_BANDWIDTH", "NIC"),
}

VALID_EDGE_SCHEMA=set(BASE_EDGE_RELATIONS)
for src_type,relation,tgt_type in BASE_EDGE_RELATIONS:
    VALID_EDGE_SCHEMA.add((tgt_type, relation, src_type))