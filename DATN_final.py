import networkx as nx
import matplotlib.pyplot as plt
import time
def read_data_values_from_file(filename):
    with open(filename, 'r') as file:
        values = file.readlines()  
        return [float(value.strip()) for value in values]
def VNFTuning(vnf_capacity, vnf_chain, data_value):
    for i in vnf_chain:
            if data_value < 0.2 * vnf_capacity[i] or data_value > 0.8 * vnf_capacity[i]:
                while data_value < 0.2 * vnf_capacity[i]:
                    vnf_capacity[i] = vnf_capacity[i] - 0.5 * vnf_capacity[i]
                while data_value > 0.8 * vnf_capacity[i]:
                    vnf_capacity[i] = vnf_capacity[i] + 0.5 * vnf_capacity[i]
    return vnf_capacity


def allocate_vnf(vnf_capacity, node_capacity, Afford_Node, data_value, vnf_chain):
    vnf_alloc = {}
    check_acceptance = True

    for f in vnf_chain:
        candidates = Afford_Node[f]
        capacity_needed = vnf_capacity[f]
        total_allocated_resources = 0
        alloc_list = []

        total_available = sum(node_capacity.get(n, 0) for n in candidates)
        if total_available < capacity_needed:
            print(f"\n❌ VNF {f} yêu cầu {capacity_needed} nhưng tổng tài nguyên các node là {total_available}. Không đủ tài nguyên.")
            check_acceptance = False
            break

        # Giai đoạn 1: Tìm node đủ sức chứa toàn bộ VNF
        candidates_enough = [n for n in candidates if node_capacity[n] >= capacity_needed]
        if candidates_enough:
            # Chọn node có dung lượng gần với nhu cầu nhất (ít dư nhất)
            best_node = min(candidates_enough, key=lambda n: node_capacity[n] - capacity_needed)
            total_allocated_resources += capacity_needed
            alloc_list.append((best_node, capacity_needed, data_value))
            print(f"[INFO] ✅ Gán toàn bộ VNF {f} vào node {best_node}")
        else:
            # Giai đoạn 2: Chia nhỏ VNF ra nhiều node
            sorted_nodes = sorted(candidates, key=lambda n: node_capacity[n], reverse=True)
            remaining = capacity_needed
            total_allocated_traffic = 0.0

            for node in sorted_nodes:
                if node_capacity[node] > 0:
                    alloc_amount = min(remaining, node_capacity[node])
                    traffic_share = data_value * (alloc_amount / capacity_needed)
                    alloc_list.append((node, alloc_amount, traffic_share))
                    total_allocated_resources += alloc_amount
                    print(f"[INFO] Gán 1 phần VNF {f} ({alloc_amount}) vào {node}")
                    remaining -= alloc_amount
                    total_allocated_traffic += traffic_share
                    if remaining <= 0:
                        break

        vnf_alloc[f] = alloc_list

    return vnf_alloc, check_acceptance, total_allocated_resources

def allocate_flow_by_cost(supply_list, demand_list, G, supply_order=None, demand_order=None):
    """
    Phân bổ lưu lượng từ các node nguồn (supply_list) đến các node đích (demand_list)
    theo chiến lược toàn cục: tính chi phí cho tất cả các cặp (nguồn, đích) và chọn cặp có chi phí thấp nhất.
    
    Nếu có hai cặp có cùng cost, ta dùng tie-breaker theo thứ tự trong vnflist (supply_order),
    Cặp có nguồn xuất hiện sớm hơn trong supply_order sẽ được ưu tiên.
    
    Input:
      - supply_list: list các tuple (node, available_flow)
      - demand_list: list các tuple (node, required_flow)
      - G: đồ thị NetworkX
      - supply_order: (optional) danh sách các node theo thứ tự ưu tiên của nguồn 
      - demand_order: (optional) danh sách các node theo thứ tự ưu tiên của đích
    Trả về: list các tuple (source, destination, allocated_flow)
    """
    # Chuyển supply và demand thành dictionary
    supply_dict = {node: flow for node, flow in supply_list}
    demand_dict = {node: flow for node, flow in demand_list}
    allocations = []
    
    while any(flow > 0 for flow in supply_dict.values()) and any(flow > 0 for flow in demand_dict.values()):
        best_pair = None
        best_cost = float('inf')
        
        # Duyệt toàn bộ các cặp (nguồn, đích) có khả năng phân bổ
        for s, s_flow in supply_dict.items():
            if s_flow <= 0:
                continue
            for d, d_flow in demand_dict.items():
                if d_flow <= 0:
                    continue
                try:
                    cost = nx.shortest_path_length(G, source=s, target=d, weight='weight')
                except nx.NetworkXNoPath:
                    continue
                # So sánh cost
                if cost < best_cost:
                    best_cost = cost
                    best_pair = (s, d)
                elif cost == best_cost:  # Nếu chi phí bằng nhau, ưu tiên theo thứ tự trong supply_order và demand_order
                    # So sánh theo thứ tự trong supply_order và demand_order nếu chi phí bằng nhau
                    if supply_order is not None and demand_order is not None:
                        # Tìm chỉ số của (s, d) trong danh sách supply_order và demand_order
                        supply_index = supply_order.index(s)
                        demand_index = demand_order.index(d)
                        
                        # Nếu nguồn s xuất hiện trước trong supply_order hoặc nguồn s cùng vị trí với đích d trong demand_order
                        if (supply_index < supply_order.index(best_pair[0])) or \
                            (supply_index == supply_order.index(best_pair[0]) and demand_index < demand_order.index(best_pair[1])):
                            best_pair = (s, d)
                    else:
                        if (s, d) < best_pair:
                            best_pair = (s, d)

        if best_pair is None:
            break
        
        s, d = best_pair
        allocated = min(supply_dict[s], demand_dict[d])
        allocations.append((s, d, allocated))
        supply_dict[s] -= allocated
        demand_dict[d] -= allocated
    return allocations

def get_paths(G, allocations):
    """
    Với mỗi phân bổ lưu lượng (s, d, flow), tìm đường đi ngắn nhất trên đồ thị G.
    Trả về danh sách các tuple (source, destination, flow, path)
    """
    paths = []
    for s, d, flow in allocations:
        path = nx.shortest_path(G, source=s, target=d, weight='weight')
        paths.append((s, d, flow, path))
    return paths

def merge_paths_to_graph(paths_stages):
    """
    Ghép các đoạn đường (path) từ các giai đoạn thành một đồ thị hợp nhất.
    Nếu một cạnh xuất hiện nhiều lần thì lưu lượng sẽ được cộng dồn.
    """
    merged_graph = nx.DiGraph()
    for stage_paths in paths_stages:
        for s, d, flow, path in stage_paths:
            for i in range(len(path) - 1):
                u = path[i]
                v = path[i+1]
                if merged_graph.has_edge(u, v):
                    merged_graph[u][v]['flow'] += flow
                else:
                    merged_graph.add_edge(u, v, flow=flow)
    return merged_graph

def draw_full_graph_with_highlight(G_original, merged_graph):
    """
    Vẽ đồ thị ban đầu và highlight phần đồ thị được ghép từ các đoạn đường định tuyến.
    Các cạnh của đồ thị ban đầu được vẽ với màu xám nhạt, sau đó overlay các cạnh của merged_graph (định tuyến)
    với màu đỏ, dày hơn và có nhãn lưu lượng.
    """
    # Lấy vị trí các node từ đồ thị gốc
    pos = nx.spring_layout(G_original, seed=42)
    plt.figure(figsize=(10, 8))
    
    nx.draw_networkx_nodes(G_original, pos, node_size=600, node_color='lightblue')
    nx.draw_networkx_labels(G_original, pos, font_size=12, font_color='black')
    nx.draw_networkx_edges(G_original, pos, edge_color='gray', style='dotted', width=1)
    
    nx.draw_networkx_edges(merged_graph, pos, edge_color='red', arrowstyle='->', arrowsize=10, width=2)
    
    edge_labels = {(u, v): f"{data['flow']:.1f}" for u, v, data in merged_graph.edges(data=True)}
    nx.draw_networkx_edge_labels(merged_graph, pos, edge_labels=edge_labels, font_color='red', font_size=10)
    
    plt.title("Đồ thị ban đầu và phần highlight từ định tuyến")
    plt.axis('off')
    plt.show()

def main():
    start_time = time.time()
    graph_edges = [
    ('NL', 'BE', 0.01), ('NL', 'DK', 0.1), ('NL', 'DE', 0.01), ('DK', 'NO', 0.01), ('DK', 'DE', 0.01),
    ('BE', 'IE', 0.01), ('CZ', 'SK', 0.1), ('CH', 'ES', 0.1), ('BG', 'MK', 6.45), ('ME', 'HR', 6.45), ('HR', 'SL', 0.01), ('NO', 'SE', 0.01),
    ('DK', 'SE', 0.01), ('DE', 'CZ', 0.01), ('DE', 'CH', 0.01), ('FR', 'CH', 0.01), ('FR', 'UK', 0.01),
    ('CH', 'IT', 0.01), ('IT', 'AT', 0.01), ('HU', 'HR', 0.01), ('HU', 'SK', 0.01), ('SK', 'AT', 0.01),
    ('SL', 'AT', 0.01), ('SE', 'FI', 0.01), ('NL', 'UK', 0.4), ('NL', 'LT', 0.4), ('DK', 'IS', 0.1),
    ('DK', 'EE', 0.1), ('DK', 'RU', 0.1), ('PL', 'UA', 1.0), ('PL', 'BY', 1.0), ('PL', 'DE', 0.1),
    ('PL', 'CZ', 0.1), ('PL', 'LT', 0.1), ('DE', 'LU', 0.1), ('DE', 'CY', 1.0), ('DE', 'IL', 0.4),
    ('DE', 'AT', 0.1), ('DE', 'RU', 0.1), ('LU', 'FR', 0.1), ('FR', 'ES', 0.1), ('IT', 'ES', 0.1),
    ('IT', 'MT', 1.0), ('IT', 'GR', 0.1), ('MD', 'RO', 1.0), ('BG', 'TR', 0.1), ('BG', 'RO', 0.1),
    ('BG', 'HU', 0.1), ('BG', 'GR', 0.1), ('RO', 'HU', 0.1), ('RO', 'TR', 0.1), ('GR', 'AT', 0.1),
    ('CY', 'UK', 1.0), ('IL', 'LT', 0.4), ('HU', 'RS', 0.1), ('PT', 'ES', 0.1), ('PT', 'UK', 0.1),
    ('LT', 'LV', 0.1), ('IS', 'UK', 0.4), ('IE', 'UK', 0.1), ('EE', 'LV', 0.1)

]

    G_original = nx.Graph()
    G_original.add_weighted_edges_from(graph_edges)
    vnf_capacity = {'f1': 10000, 'f2': 8000, 'f3': 6000, 'f4': 12000}
    vnf_chain = ['f1', 'f2', 'f3', 'f4']
    node_capacity = {'IE': 16000, 'UA': 16000, 'UK': 10000, 'NL': 10000, 'IS': 10000, 'DK': 10000, 'LU': 8000, 'DE': 8000, 'IL':8000, 'CZ': 8000, 'MD': 12000, 'RO': 12000, 'ES': 12000, 'BG': 12000, 'GR': 12000}
    Afford_Node = {
        'f1': ['IE', 'UA'],
        'f2': ['UK', 'NL', 'IS', 'DK'],
        'f3': ['LU', 'DE', 'IL', 'CZ'],
        'f4': ['MD', 'RO' ,'ES', 'BG', 'GR']
    }

    counting_accept = 0
    data_values = read_data_values_from_file('input1.txt')
    source = 'BE'
    destination = 'IT'
    total_resources_used = 0
    for data_value in data_values:
        print("Thực hiện với DataValue =", data_value)
        vnf_capacity_after = VNFTuning(vnf_capacity, vnf_chain, data_value)
    # --- Bước 1: Phân bổ VNF và tính lưu lượng qua các node ---
        for i in vnf_chain:
            print('TN cần thiết cho VNF', i, 'là', vnf_capacity_after[i])
        vnf_alloc, check_acceptance, total_allocated_resources = allocate_vnf(vnf_capacity_after, node_capacity, Afford_Node, data_value,vnf_chain)
        total_resources_used += total_allocated_resources
        if check_acceptance:
            counting_accept += 1
            print("Phân bổ VNF và lưu lượng:")
            for f in vnf_chain:
                print(f"  VNF {f}:")
                for node, allocated, traffic in vnf_alloc[f]:
                    print(f"    Node {node}: allocated = {allocated}, traffic = {traffic:.2f}")
            
            # --- Bước 2: Phân bổ lưu lượng qua các giai đoạn định tuyến ---
            all_stage_paths = []
            
            # Giai đoạn 0: Từ nguồn đến VNF đầu tiên
            supply = [(source, data_value)]
            demand = [(node, traffic) for node, _, traffic in vnf_alloc[vnf_chain[0]]]
            alloc = allocate_flow_by_cost(supply, demand, G_original)
            paths = get_paths(G_original, alloc)
            all_stage_paths.append(paths)
            
            # Các giai đoạn giữa: từ VNF[i-1] đến VNF[i]
            for i in range(1, len(vnf_chain)):
                supply = [(node, traffic) for node, _, traffic in vnf_alloc[vnf_chain[i-1]]]
                demand = [(node, traffic) for node, _, traffic in vnf_alloc[vnf_chain[i]]]
                alloc = allocate_flow_by_cost(supply, demand, G_original)
                paths = get_paths(G_original, alloc)
                all_stage_paths.append(paths)
            
            # Giai đoạn cuối: Từ VNF cuối cùng đến đích
            supply = [(node, traffic) for node, _, traffic in vnf_alloc[vnf_chain[-1]]]
            demand = [(destination, data_value)]
            alloc = allocate_flow_by_cost(supply, demand, G_original)
            paths = get_paths(G_original, alloc)
            all_stage_paths.append(paths)
            
            # Hiển thị thông tin định tuyến từng giai đoạn
            stage_names = ["Nguồn -> " + vnf_chain[0]] + \
                        [vnf_chain[i-1] + " -> " + vnf_chain[i] for i in range(1, len(vnf_chain))] + \
                        [vnf_chain[-1] + " -> Đích"]
            for stage, paths in zip(stage_names, all_stage_paths):
                print(f"\nGiai đoạn {stage}:")
                for s, d, flow, path in paths:
                    print(f"  Đường {path} với lưu lượng = {flow:.2f}")
            print("-----------------------------------\n")

            # merged_graph = merge_paths_to_graph(all_stage_paths)
            # draw_full_graph_with_highlight(G_original, merged_graph)

    acceptance_ratio = counting_accept/len(data_values) * 100
    violation_ratio = 100 - acceptance_ratio
    print("Acceptance Ratio for test:",acceptance_ratio,"%")
    print("SLA Violation Ratio for test:",violation_ratio,"%")
    print(f"Tổng tài nguyên đã sử dụng: {total_resources_used}")
    end_time = time.time()  # Ghi lại thời gian kết thúc
    execution_time = end_time - start_time  # Tính thời gian thực thi
    average_proccessing_time = execution_time/len(data_values)
    print(f"Thời gian xử lý trung bình: {average_proccessing_time:.6f} giây")
    with open("DynamicSFCTuning.txt", "w", encoding="utf-8") as file:
        file.write(f"Acceptance Ratio for test: {acceptance_ratio}%\n")
        file.write(f"SLA Violation Ratio for test: {violation_ratio}%\n")
        file.write(f"Tổng tài nguyên đã sử dụng: {total_resources_used}\n")
        file.write(f"Thời gian xử lý trung bình: {average_proccessing_time:.6f} giây\n")
if __name__ == "__main__":
    main()
