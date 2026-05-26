
BASE_EDGE_RELATIONS = {

    # CPU 访问主内存
    ("CPU", "LOCAL_MEMORY", "MEMORY"),
    # CPU 连接本地 NIC
    ("CPU", "LOCAL_NIC", "NIC"),
    # CPU 通过 PCIe 连接 GPU
    ("CPU", "PCIE", "GPU"),
    # GPU 访问主机内存
    ("GPU", "HOST_MEMORY", "MEMORY"),
    # GPU 访问网络
    ("GPU", "NETWORK_ACCESS", "NIC"),

    # CPU 通过 PCIe 连接 FPGA
    ("CPU", "PCIE_FPGA", "FPGA"),
    # FPGA 访问主机内存
    ("FPGA", "HOST_MEMORY", "MEMORY"),
    # FPGA 访问网络
    ("FPGA", "NETWORK_ACCESS", "NIC"),


    # CPU 访问本地存储
    ("CPU", "LOCAL_STORAGE", "STORAGE"),
    # GPU 访问存储，表示 IO 访问，不一定是物理直连
    ("GPU", "IO_ACCESS", "STORAGE"),
    # STORAGE 通过 NIC 访问网络
    ("STORAGE", "NETWORK_ACCESS", "NIC"),

    #同宿主
    ("CPU", "SAME_HOST", "GPU"),
    ("CPU", "SAME_HOST", "FPGA"),
    ("CPU", "SAME_HOST", "MEMORY"),
    ("CPU", "SAME_HOST", "NIC"),
    ("CPU", "SAME_HOST", "STORAGE"),
    ("GPU", "SAME_HOST", "MEMORY"),
    ("GPU", "SAME_HOST", "NIC"),
    ("GPU", "SAME_HOST", "STORAGE"),
    ("FPGA", "SAME_HOST", "MEMORY"),
    ("FPGA", "SAME_HOST", "NIC"),
    ("STORAGE", "SAME_HOST", "NIC"),

    #不同机器之间的topo
    ("NIC", "CONNECTED_TO", "SWITCH"),
    ("SWITCH", "CONNECTED_TO", "SWITCH"),

    #同机架拓扑关系
    ("SWITCH", "SAME_RACK", "SWITCH"),
    ("CPU", "SAME_RACK", "CPU"),
    ("GPU", "SAME_RACK", "GPU"),
    ("FPGA", "SAME_RACK", "FPGA"),
    ("NIC", "SAME_RACK", "NIC"),

    # 低延迟互联关系
    ("CPU", "LOW_LATENCY_LINK", "CPU"),
    ("GPU", "LOW_LATENCY_LINK", "GPU"),
    ("FPGA", "LOW_LATENCY_LINK", "FPGA"),

    #资源竞争关系
    #这类边不是通信路径，而是约束/竞争关系
    ("GPU", "COMPETES_BANDWIDTH", "GPU"),
    ("GPU", "COMPETES_BANDWIDTH", "NIC"),
    ("FPGA", "COMPETES_BANDWIDTH", "NIC"),
    ("STORAGE", "COMPETES_BANDWIDTH", "NIC"),

    ("CPU", "COMPETES_MEMORY", "CPU"),
    ("GPU", "COMPETES_MEMORY", "GPU"),
}

VALID_EDGE_RELATIONS=BASE_EDGE_RELATIONS
