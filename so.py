import os
import struct

class FURGfs2:
    def __init__(self, caminho, tamanho):
        self.caminho = caminho
        self.tamanho = tamanho
        self.tamanho_bloco = 512  # Tamanho fixo de bloco
        self.tamanho_cabecalho = 1024  # Espaço reservado para o cabeçalho
        self.inicio_fat = self.tamanho_cabecalho  # FAT começa logo após o cabeçalho
        self.tamanho_maximo_nome = 50  # Tamanho máximo do nome de arquivos
        self.inicio_diretorio = self.inicio_fat + (self.tamanho // self.tamanho_bloco) * 4  # FAT com 4 bytes por entrada
        self.inicio_dados = self.inicio_diretorio + (self.tamanho // self.tamanho_bloco) * 64  # Diretório raiz
        self.inicializar_sistema_arquivo()

    def inicializar_sistema_arquivo(self):
        """Inicializa o sistema de arquivos."""
        if os.path.exists(self.caminho):
            print("O sistema de arquivos já existe.")
            return
        with open(self.caminho, "wb") as arquivo:
            # Cria o arquivo vazio
            arquivo.write(b'\x00' * self.tamanho)
            # Escreve o cabeçalho
            arquivo.seek(0)
            arquivo.write(struct.pack("I", self.tamanho))
            arquivo.write(struct.pack("I", self.tamanho_bloco))
            arquivo.write(struct.pack("I", self.tamanho_cabecalho))
            arquivo.write(struct.pack("I", self.inicio_fat))
            arquivo.write(struct.pack("I", self.inicio_diretorio))
            arquivo.write(struct.pack("I", self.inicio_dados))

    def listar_arquivos(self):
        """Lista os arquivos armazenados no sistema."""
        with open(self.caminho, "rb") as arquivo:
            arquivo.seek(self.inicio_diretorio)
            arquivos = []
            for _ in range(self.tamanho // self.tamanho_bloco):
                entrada = arquivo.read(64)
                if entrada[0] != 0:  # Verifica se é uma entrada válida
                    nome = entrada[:self.tamanho_maximo_nome].decode("utf-8").strip('\x00')
                    arquivos.append(nome)
            return arquivos

    def listar_espaco_livre(self):
        """Lista o espaço livre em relação ao total do FURGfs2."""
        with open(self.caminho, "rb") as arquivo:
            arquivo.seek(self.inicio_fat)
            fat = [struct.unpack("I", arquivo.read(4))[0] for _ in range(self.tamanho // self.tamanho_bloco)]
            blocos_livres = fat.count(0)
            espaco_livre = blocos_livres * self.tamanho_bloco
            espaco_total = self.tamanho
            espaco_livre_mb = espaco_livre // (1024 * 1024)
            espaco_total_mb = espaco_total // (1024 * 1024)
            return f"{espaco_livre_mb}MB livres de {espaco_total_mb}MB"

    def copiar_para_sistema(self, caminho_origem, nome_destino):
        """Copia um arquivo do sistema real para o FURGfs2."""
        if not os.path.exists(caminho_origem):
            raise FileNotFoundError(f"Arquivo de origem '{caminho_origem}' não encontrado.")
        
        with open(caminho_origem, "rb") as origem:
            dados = origem.read()
            tamanho_arquivo = len(dados)
            blocos_necessarios = (tamanho_arquivo + self.tamanho_bloco - 1) // self.tamanho_bloco

            with open(self.caminho, "r+b") as arquivo:
                # Lê e atualiza FAT
                arquivo.seek(self.inicio_fat)
                fat = [struct.unpack("I", arquivo.read(4))[0] for _ in range(self.tamanho // self.tamanho_bloco)]
                blocos_livres = [i for i, entrada in enumerate(fat) if entrada == 0]

                if len(blocos_livres) < blocos_necessarios:
                    raise Exception("Espaço insuficiente no FURGfs2.")

                # Atualiza o diretório
                arquivo.seek(self.inicio_diretorio)
                for _ in range(self.tamanho // self.tamanho_bloco):
                    entrada = arquivo.read(64)
                    if entrada[0] == 0:  # Entrada vazia
                        arquivo.seek(-64, os.SEEK_CUR)
                        arquivo.write(nome_destino.ljust(self.tamanho_maximo_nome, '\x00').encode("utf-8"))
                        arquivo.write(struct.pack("I", tamanho_arquivo))
                        arquivo.write(struct.pack("I", blocos_livres[0]))
                        break

                # Escreve os dados nos blocos
                for i, bloco in enumerate(blocos_livres[:blocos_necessarios]):
                    arquivo.seek(self.inicio_dados + bloco * self.tamanho_bloco)
                    arquivo.write(dados[i * self.tamanho_bloco:(i + 1) * self.tamanho_bloco])
                    fat[bloco] = blocos_livres[i + 1] if i + 1 < blocos_necessarios else -1

                # Atualiza FAT
                arquivo.seek(self.inicio_fat)
                for entrada in fat:
                    arquivo.write(struct.pack("I", entrada))

    def copiar_do_sistema(self, nome_origem, caminho_destino):
        """Copia um arquivo do FURGfs2 para o sistema de arquivos real."""
        with open(self.caminho, "rb") as arquivo:
            arquivo.seek(self.inicio_diretorio)
            for _ in range(self.tamanho // self.tamanho_bloco):
                entrada = arquivo.read(64)
                nome = entrada[:self.tamanho_maximo_nome].decode("utf-8").strip('\x00')
                if nome == nome_origem:
                    tamanho_arquivo, primeiro_bloco = struct.unpack("II", entrada[self.tamanho_maximo_nome:self.tamanho_maximo_nome + 8])
                    dados = bytearray()
                    while primeiro_bloco != -1:
                        arquivo.seek(self.inicio_dados + primeiro_bloco * self.tamanho_bloco)
                        dados += arquivo.read(self.tamanho_bloco)
                        arquivo.seek(self.inicio_fat + primeiro_bloco * 4)
                        primeiro_bloco = struct.unpack("I", arquivo.read(4))[0]
                    with open(caminho_destino, "wb") as destino:
                        destino.write(dados[:tamanho_arquivo])
                    return
            raise FileNotFoundError("Arquivo não encontrado no FURGfs2.")

    def renomear_arquivo(self, nome_atual, novo_nome):
        """Renomeia um arquivo armazenado no FURGfs2."""
        with open(self.caminho, "r+b") as arquivo:
            arquivo.seek(self.inicio_diretorio)
            for _ in range(self.tamanho // self.tamanho_bloco):
                entrada = arquivo.read(64)
                nome = entrada[:self.tamanho_maximo_nome].decode("utf-8").strip('\x00')
                if nome == nome_atual:
                    arquivo.seek(-64, os.SEEK_CUR)
                    arquivo.write(novo_nome.ljust(self.tamanho_maximo_nome, '\x00').encode("utf-8"))
                    return
            raise FileNotFoundError("Arquivo não encontrado no FURGfs2.")

    def remover_arquivo(self, nome_arquivo):
        """Remove um arquivo armazenado no FURGfs2."""
        with open(self.caminho, "r+b") as arquivo:
            arquivo.seek(self.inicio_diretorio)
            for _ in range(self.tamanho // self.tamanho_bloco):
                entrada = arquivo.read(64)
                nome = entrada[:self.tamanho_maximo_nome].decode("utf-8").strip('\x00')
                if nome == nome_arquivo:
                    # Marca como removido
                    arquivo.seek(-64, os.SEEK_CUR)
                    arquivo.write(b'\x00' * 64)
                    return
            raise FileNotFoundError("Arquivo não encontrado no FURGfs2.")

    def proteger_arquivo(self, nome_arquivo, proteger=True):
        """Protege ou desprotege um arquivo contra remoção/escrita."""
        with open(self.caminho, "r+b") as arquivo:
            arquivo.seek(self.inicio_diretorio)
            for _ in range(self.tamanho // self.tamanho_bloco):
                entrada = arquivo.read(64)
                nome = entrada[:self.tamanho_maximo_nome].decode("utf-8").strip('\x00')
                if nome == nome_arquivo:
                    arquivo.seek(-64, os.SEEK_CUR)
                    protecao = 1 if proteger else 0
                    arquivo.write(struct.pack("B", protecao))
                    return
            raise FileNotFoundError("Arquivo não encontrado no FURGfs2.")


def main():
    print("Bem-vindo ao FURGfs2!")
    caminho = input("Digite o nome do arquivo do sistema de arquivos (e.g., furgfs2.fs): ")
    tamanho_mb = int(input("Digite o tamanho do sistema de arquivos em MB (mínimo 6MB): "))
    if tamanho_mb < 6:
        print("O tamanho mínimo do sistema de arquivos é 6MB.")
        return
    tamanho_bytes = tamanho_mb * 1024 * 1024
    fs = FURGfs2(caminho, tamanho_bytes)
    print(f"Sistema de arquivos '{caminho}' criado ou carregado com sucesso!")

    while True:
        print("\nEscolha uma opção:")
        print("1. Copiar arquivo para dentro do FURGfs2")
        print("2. Copiar arquivo do FURGfs2 para o sistema real")
        print("3. Renomear arquivo no FURGfs2")
        print("4. Remover arquivo no FURGfs2")
        print("5. Listar arquivos no FURGfs2")
        print("6. Mostrar espaço livre no FURGfs2")
        print("7. Proteger/desproteger arquivo")
        print("8. Sair")

        opcao = input("Digite a opção desejada: ")

        try:
            if opcao == "1":
                origem = input("Digite o caminho do arquivo no sistema real: ")
                destino = input("Digite o nome do arquivo no FURGfs2: ")
                fs.copiar_para_sistema(origem, destino)
                print("Arquivo copiado com sucesso!")
            elif opcao == "2":
                origem = input("Digite o nome do arquivo no FURGfs2: ")
                destino = input("Digite o caminho de destino no sistema real: ")
                fs.copiar_do_sistema(origem, destino)
                print("Arquivo copiado com sucesso!")
            elif opcao == "3":
                nome_atual = input("Digite o nome atual do arquivo: ")
                novo_nome = input("Digite o novo nome para o arquivo: ")
                fs.renomear_arquivo(nome_atual, novo_nome)
                print("Arquivo renomeado com sucesso!")
            elif opcao == "4":
                nome = input("Digite o nome do arquivo a ser removido: ")
                fs.remover_arquivo(nome)
                print("Arquivo removido com sucesso!")
            elif opcao == "5":
                arquivos = fs.listar_arquivos()
                print("Arquivos armazenados no FURGfs2:")
                for arquivo in arquivos:
                    print(f"- {arquivo}")
            elif opcao == "6":
                espaco = fs.listar_espaco_livre()
                print(espaco)
            elif opcao == "7":
                nome = input("Digite o nome do arquivo: ")
                acao = input("Digite 'proteger' para proteger ou 'desproteger' para remover proteção: ").strip().lower()
                proteger = True if acao == "proteger" else False
                fs.proteger_arquivo(nome, proteger)
                print("Ação concluída com sucesso!")
            elif opcao == "8":
                print("Saindo...")
                break
            else:
                print("Opção inválida, tente novamente.")
        except Exception as e:
            print(f"Erro: {e}")

if __name__ == "__main__":
    main()