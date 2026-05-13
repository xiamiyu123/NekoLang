// neko_tcp_adapter.c - 为 socket_adapter_demo 提供一个极小的 TCP 文本客户端

#include <arpa/inet.h>
#include <netinet/in.h>
#include <stdlib.h>
#include <string.h>
#include <sys/socket.h>
#include <sys/types.h>
#include <unistd.h>

struct neko_tcp_client {
    int fd;
};

// 连接到指定主机和端口，成功时返回一个堆分配的 client 句柄。
void *neko_tcp_connect(const char *host, int port) {
    int fd = socket(AF_INET, SOCK_STREAM, 0);
    if (fd < 0) {
        return NULL;
    }

    struct sockaddr_in addr;
    memset(&addr, 0, sizeof(addr));
    addr.sin_family = AF_INET;
    addr.sin_port = htons((unsigned short)port);
    if (inet_pton(AF_INET, host, &addr.sin_addr) != 1) {
        close(fd);
        return NULL;
    }
    if (connect(fd, (struct sockaddr *)&addr, sizeof(addr)) != 0) {
        close(fd);
        return NULL;
    }

    struct neko_tcp_client *client = malloc(sizeof(*client));
    if (client == NULL) {
        close(fd);
        return NULL;
    }
    client->fd = fd;
    return client;
}

// 发送一行文本；为了便于做 echo 示例，这里会自动补一个换行。
int neko_tcp_send_text(void *handle, const char *text) {
    if (handle == NULL || text == NULL) {
        return 0;
    }

    struct neko_tcp_client *client = handle;
    size_t len = strlen(text);
    if (send(client->fd, text, len, 0) < 0) {
        return 0;
    }
    if (send(client->fd, "\n", 1, 0) < 0) {
        return 0;
    }
    return 1;
}

// 持续读取直到遇到换行，返回一段以 '\0' 结尾的 C 字符串。
char *neko_tcp_recv_line(void *handle) {
    if (handle == NULL) {
        char *empty = malloc(1);
        if (empty != NULL) {
            empty[0] = '\0';
        }
        return empty;
    }

    struct neko_tcp_client *client = handle;
    size_t cap = 256;
    size_t len = 0;
    char *buffer = malloc(cap);
    if (buffer == NULL) {
        return NULL;
    }

    while (1) {
        char ch = '\0';
        ssize_t n = recv(client->fd, &ch, 1, 0);
        if (n <= 0) {
            break;
        }
        if (ch == '\n') {
            break;
        }
        if (len + 1 >= cap) {
            cap *= 2;
            char *grown = realloc(buffer, cap);
            if (grown == NULL) {
                free(buffer);
                return NULL;
            }
            buffer = grown;
        }
        buffer[len++] = ch;
    }

    buffer[len] = '\0';
    return buffer;
}

// 关闭 socket 并释放前面分配的 client 结构体。
int neko_tcp_close(void *handle) {
    if (handle == NULL) {
        return 0;
    }

    struct neko_tcp_client *client = handle;
    int ok = close(client->fd) == 0;
    free(client);
    return ok ? 1 : 0;
}
