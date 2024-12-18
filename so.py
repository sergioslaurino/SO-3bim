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
            blocos_livres = fat.count(0)  # Conta o número de blocos livres (onde a FAT é 0)
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

                # Verificação de espaço
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
                    if bloco == -1:
                        break
                    arquivo.seek(self.inicio_dados + bloco * self.tamanho_bloco)
                    arquivo.write(dados[i * self.tamanho_bloco:(i + 1) * self.tamanho_bloco])

                    # Atualiza a FAT para o próximo bloco, se necessário
                    if i + 1 <= blocos_necessarios:
                        fat[bloco] = blocos_livres[i + 1]
                    else:
                        fat[bloco] = -1  # Marca o final do arquivo

                # Atualiza a FAT
                arquivo.seek(self.inicio_fat)
                for entrada in fat:
                    arquivo.write(struct.pack("I", entrada))

                # Atualiza o espaço livre
                espaco_livre_atualizado = self.listar_espaco_livre()
                print(f"Espaço livre após a cópia: {espaco_livre_atualizado}")

                print("Arquivo copiado e FAT atualizada!")



    def copiar_do_sistema(self, nome_origem, caminho_destino):
        """Copia um arquivo do FURGfs2 para o sistema de arquivos real."""
        with open(self.caminho, "rb") as arquivo:
            arquivo.seek(self.inicio_diretorio)
            for _ in range(self.tamanho // self.tamanho_bloco):
                entrada = arquivo.read(64)
                nome = entrada[:self.tamanho_maximo_nome].decode("utf-8").strip('\x00')
                if nome == nome_origem:
                    tamanho_arquivo, primeiro_bloco = struct.unpack("II", entrada[self.tamanho_maximo_nome:self.tamanho_maximo_nome + 8])
                    
                    # Abre o destino para gravação enquanto lê os dados em blocos
                    with open(caminho_destino, "wb") as destino:
                        while primeiro_bloco != -1:
                            arquivo.seek(self.inicio_dados + primeiro_bloco * self.tamanho_bloco)
                            bloco = arquivo.read(self.tamanho_bloco)
                            bytes_a_escrever = min(len(bloco), tamanho_arquivo)
                            destino.write(bloco[:bytes_a_escrever])
                            
                            tamanho_arquivo -= bytes_a_escrever
                            if tamanho_arquivo <= 0:
                                break
                            
                            arquivo.seek(self.inicio_fat + primeiro_bloco * 4)
                            primeiro_bloco = struct.unpack("I", arquivo.read(4))[0]
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
        """Remove um arquivo armazenado no FURGfs2 e libera o espaço ocupado na FAT."""
        with open(self.caminho, "r+b") as arquivo:
            arquivo.seek(self.inicio_diretorio)
            
            # Percorre o diretório em busca do arquivo
            for _ in range(self.tamanho // self.tamanho_bloco):
                entrada = arquivo.read(64)
                nome = entrada[:self.tamanho_maximo_nome].decode("utf-8").strip('\x00')
                if nome == nome_arquivo:
                    # Obtém o tamanho e o primeiro bloco a partir da entrada
                    tamanho_arquivo, primeiro_bloco = struct.unpack("II", entrada[self.tamanho_maximo_nome:self.tamanho_maximo_nome + 8])
                    
                    # Calcula o número de blocos necessários para armazenar o arquivo
                    blocos_necessarios = (tamanho_arquivo + self.tamanho_bloco - 1) // self.tamanho_bloco

                    # Agora, vamos liberar esses blocos
                    arquivo.seek(self.inicio_fat)
                    bloco_atual = primeiro_bloco
                    for _ in range(blocos_necessarios):
                        if bloco_atual == -1:
                            break
                        
                        # Marca o bloco atual como livre (0) na FAT
                        arquivo.seek(self.inicio_fat + bloco_atual * 4)
                        arquivo.write(struct.pack("I", 0))  # Marca como livre

                        # Vai para o próximo bloco na FAT
                        arquivo.seek(self.inicio_fat + bloco_atual * 4)
                        bloco_atual = struct.unpack("I", arquivo.read(4))[0]

                    # Limpa a entrada do arquivo no diretório (marca como vazio)
                    arquivo.seek(self.inicio_diretorio)
                    for i in range(self.tamanho // self.tamanho_bloco):
                        entrada = arquivo.read(64)
                        nome = entrada[:self.tamanho_maximo_nome].decode("utf-8").strip('\x00')
                        if nome == nome_arquivo:
                            arquivo.seek(self.inicio_diretorio + i * 64)
                            arquivo.write(b'\x00' * 64)  # Limpa a entrada
                            break

                    print(f"Arquivo '{nome_arquivo}' removido e espaço liberado com sucesso!")
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
                destino = input("Digite o caminho para salvar no sistema real: ")
                fs.copiar_do_sistema(origem, destino)
                print("Arquivo copiado com sucesso!")
            elif opcao == "3":
                nome_atual = input("Digite o nome atual do arquivo no FURGfs2: ")
                novo_nome = input("Digite o novo nome para o arquivo: ")
                fs.renomear_arquivo(nome_atual, novo_nome)
                print("Arquivo renomeado com sucesso!")
            elif opcao == "4":
                nome_arquivo = input("Digite o nome do arquivo no FURGfs2 para remover: ")
                fs.remover_arquivo(nome_arquivo)
                print("Arquivo removido com sucesso!")
            elif opcao == "5":
                arquivos = fs.listar_arquivos()
                print("Arquivos no FURGfs2:", arquivos)
            elif opcao == "6":
                espaco_livre = fs.listar_espaco_livre()
                print("Espaço livre:", espaco_livre)
            elif opcao == "7":
                nome_arquivo = input("Digite o nome do arquivo para proteger/desproteger: ")
                proteger = input("Proteger o arquivo? (s/n): ").strip().lower() == 's'
                fs.proteger_arquivo(nome_arquivo, proteger)
                print(f"Arquivo {'protegido' if proteger else 'desprotegido'} com sucesso!")
            elif opcao == "8":
                print("Saindo do sistema de arquivos.")
                break
            else:
                print("Opção inválida!")
        except Exception as e:
            print(f"Erro: {e}")

# Execute o main
if __name__ == "__main__":
    main()