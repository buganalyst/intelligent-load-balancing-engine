#include <iostream>
#include <vector>
#include <string>
#include <sstream>
#include <algorithm>
#include <cmath>
#include <map>
#include <cstdlib>
#include <ctime>

using namespace std;

struct Server {
    string url;
    int weight;
    int connections;
    bool health;
};

class LoadBalancer {
private:
    vector<Server> servers;
    int rr_index;
    int wrr_index;
    vector<string> wrr_list;

public:
    LoadBalancer() {
        rr_index = 0;
        wrr_index = 0;
        srand(time(NULL));
    }

    void addServer(string url, int weight, int connections, bool health) {
        Server s;
        s.url = url;
        s.weight = weight;
        s.connections = connections;
        s.health = health;
        servers.push_back(s);
        
        for (int i = 0; i < weight; i++) {
            wrr_list.push_back(url);
        }
    }

    string roundRobin() {
        if (servers.empty()) return "";
        int n = servers.size();
        int attempts = 0;
        while (attempts < n) {
            int idx = rr_index % n;
            if (servers[idx].health) {
                rr_index = (rr_index + 1) % n;
                return servers[idx].url;
            }
            rr_index = (rr_index + 1) % n;
            attempts++;
        }
        return servers[0].url;
    }

    string weightedRoundRobin() {
        if (wrr_list.empty()) return "";
        int n = wrr_list.size();
        int attempts = 0;
        while (attempts < n) {
            int idx = wrr_index % n;
            string url = wrr_list[idx];
            if (getServerHealth(url)) {
                wrr_index = (wrr_index + 1) % n;
                return url;
            }
            wrr_index = (wrr_index + 1) % n;
            attempts++;
        }
        return wrr_list[0];
    }

    string leastConnections() {
        int min_conn = 2147483647;
        string selected = "";
        for (const auto& s : servers) {
            if (s.health) {
                if (s.connections < min_conn) {
                    min_conn = s.connections;
                    selected = s.url;
                }
            }
        }
        if (selected == "") return servers[0].url;
        return selected;
    }

    string ipHash(string ip) {
        if (servers.empty()) return "";
        long long hash = 0;
        for (char c : ip) {
            hash = (hash * 31 + c) % 1000000007;
        }
        int idx = abs((int)(hash % servers.size()));
        if (servers[idx].health) return servers[idx].url;
        
        for (int i = 1; i < servers.size(); i++) {
            int next_idx = (idx + i) % servers.size();
            if (servers[next_idx].health) return servers[next_idx].url;
        }
        return servers[0].url;
    }

    string randomSelection() {
        vector<string> healthy;
        for (const auto& s : servers) {
            if (s.health) {
                healthy.push_back(s.url);
            }
        }
        if (healthy.empty()) return servers[0].url;
        int idx = rand() % healthy.size();
        return healthy[idx];
    }

    bool getServerHealth(string url) {
        for (const auto& s : servers) {
            if (s.url == url) return s.health;
        }
        return false;
    }
};

int main(int argc, char* argv[]) {
    if (argc < 2) {
        cout << "ERROR: No algorithm specified" << endl;
        return 1;
    }

    string algo = argv[1];
    string ip = (argc > 2) ? argv[2] : "127.0.0.1";
    
    LoadBalancer lb;
    string line;
    
    while (getline(cin, line)) {
        if (line.empty()) break;
        stringstream ss(line);
        string url;
        int weight, conn;
        bool health;
        char comma;
        ss >> url >> comma >> weight >> comma >> conn >> comma >> health;
        lb.addServer(url, weight, conn, health);
    }

    string result = "";
    if (algo == "round_robin") result = lb.roundRobin();
    else if (algo == "weighted_round_robin") result = lb.weightedRoundRobin();
    else if (algo == "least_connections") result = lb.leastConnections();
    else if (algo == "ip_hash") result = lb.ipHash(ip);
    else if (algo == "random") result = lb.randomSelection();
    else result = lb.roundRobin();

    cout << result << endl;
    return 0;
}
