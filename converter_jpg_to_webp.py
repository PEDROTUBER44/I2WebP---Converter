#!/usr/bin/env python3
"""
Script para converter imagens de vários formatos para WebP com compressão de 80%
Processa todas as imagens da pasta onde o script está localizado
Suporta: JPG, JPEG, PNG, BMP, TIFF, GIF, ICO, WEBP
PRESERVA METADADOS EXIF e outras informações da imagem original

Dependências necessárias:
pip install Pillow piexif
"""

import os
from PIL import Image
import glob
import piexif
import json
from datetime import datetime

def clean_exif_data(exif_dict):
    """
    Limpa e valida dados EXIF para compatibilidade com WebP
    
    Args:
        exif_dict (dict): Dicionário EXIF original
        
    Returns:
        dict: Dicionário EXIF limpo e compatível
    """
    if not exif_dict:
        return None
    
    try:
        # Lista de tags problemáticas que devem ser removidas
        problematic_tags = {
            41729,  # ColorSpace - frequentemente causa problemas
            40961,  # ColorSpace alternativo
            40962,  # PixelXDimension
            40963,  # PixelYDimension
            34665,  # ExifIFD (pode causar recursão)
            34853,  # GPSIFD (pode ser problemático)
        }
        
        cleaned_dict = {}
        
        for ifd_name, ifd_data in exif_dict.items():
            if isinstance(ifd_data, dict):
                cleaned_ifd = {}
                for tag_id, tag_value in ifd_data.items():
                    # Pula tags problemáticas
                    if tag_id in problematic_tags:
                        continue
                    
                    # Valida tipos de dados
                    if isinstance(tag_value, (bytes, str, int, tuple)):
                        # Verifica se é uma string/bytes válida
                        if isinstance(tag_value, bytes):
                            try:
                                # Tenta decodificar para verificar se é válido
                                tag_value.decode('utf-8', errors='ignore')
                                cleaned_ifd[tag_id] = tag_value
                            except:
                                continue
                        elif isinstance(tag_value, str):
                            # Converte string para bytes se necessário
                            cleaned_ifd[tag_id] = tag_value.encode('utf-8')
                        elif isinstance(tag_value, int):
                            # Valida valores inteiros
                            if -2147483648 <= tag_value <= 2147483647:  # int32 range
                                cleaned_ifd[tag_id] = tag_value
                        elif isinstance(tag_value, tuple):
                            # Valida tuplas (geralmente frações)
                            if len(tag_value) == 2 and all(isinstance(x, int) for x in tag_value):
                                if all(-2147483648 <= x <= 2147483647 for x in tag_value):
                                    cleaned_ifd[tag_id] = tag_value
                
                if cleaned_ifd:
                    cleaned_dict[ifd_name] = cleaned_ifd
            else:
                # Para dados não-dict, apenas mantém se for um tipo básico
                if isinstance(ifd_data, (bytes, str, int)):
                    cleaned_dict[ifd_name] = ifd_data
        
        return cleaned_dict if cleaned_dict else None
        
    except Exception as e:
        print(f"    ⚠️  Erro ao limpar dados EXIF: {e}")
        return None

def extract_all_metadata(image_path):
    """
    Extrai todos os metadados possíveis de uma imagem
    
    Args:
        image_path (str): Caminho da imagem
        
    Returns:
        dict: Dicionário com todos os metadados encontrados
    """
    metadata = {
        'exif': None,
        'icc_profile': None,
        'xmp': None,
        'other_info': {}
    }
    
    try:
        with Image.open(image_path) as img:
            # Extrai EXIF usando piexif
            if 'exif' in img.info:
                try:
                    exif_dict = piexif.load(img.info['exif'])
                    # Limpa os dados EXIF
                    metadata['exif'] = clean_exif_data(exif_dict)
                except Exception as e:
                    print(f"    ⚠️  Erro ao extrair EXIF: {e}")
            
            # Extrai perfil ICC
            if 'icc_profile' in img.info:
                metadata['icc_profile'] = img.info['icc_profile']
            
            # Extrai XMP
            if 'xmp' in img.info:
                metadata['xmp'] = img.info['xmp']
            
            # Extrai outras informações
            for key, value in img.info.items():
                if key not in ['exif', 'icc_profile', 'xmp']:
                    metadata['other_info'][key] = value
                    
    except Exception as e:
        print(f"    ⚠️  Erro ao extrair metadados: {e}")
    
    return metadata

def get_creation_datetime_from_exif(exif_dict):
    """
    Extrai a data/hora de criação da foto dos dados EXIF
    
    Args:
        exif_dict (dict): Dicionário EXIF
        
    Returns:
        str or None: Data/hora formatada ou None se não encontrada
    """
    if not exif_dict:
        return None
    
    try:
        # Procura por informações de data em diferentes campos EXIF
        datetime_tags = [
            ('Exif', piexif.ExifIFD.DateTimeOriginal),  # Data original da foto
            ('Exif', piexif.ExifIFD.DateTimeDigitized), # Data de digitalização
            ('0th', piexif.ImageIFD.DateTime)           # Data de modificação
        ]
        
        for ifd_name, tag_id in datetime_tags:
            if ifd_name in exif_dict and tag_id in exif_dict[ifd_name]:
                datetime_value = exif_dict[ifd_name][tag_id]
                if isinstance(datetime_value, bytes):
                    datetime_str = datetime_value.decode('utf-8', errors='ignore').strip()
                elif isinstance(datetime_value, str):
                    datetime_str = datetime_value.strip()
                else:
                    continue
                
                # Retorna a primeira data válida encontrada
                if datetime_str and datetime_str != '0000:00:00 00:00:00':
                    return datetime_str
                    
    except Exception as e:
        print(f"    ⚠️  Erro ao extrair data/hora: {e}")
    
    return None

def set_file_timestamps(file_path, creation_datetime):
    """
    Define os timestamps do arquivo baseado na data EXIF
    
    Args:
        file_path (str): Caminho do arquivo
        creation_datetime (str): Data/hora no formato EXIF (YYYY:MM:DD HH:MM:SS)
    """
    if not creation_datetime:
        return
    
    try:
        # Converte formato EXIF para datetime
        dt = datetime.strptime(creation_datetime, '%Y:%m:%d %H:%M:%S')
        timestamp = dt.timestamp()
        
        # Define timestamps de modificação e acesso
        os.utime(file_path, (timestamp, timestamp))
        print(f"    📅 Timestamps ajustados para: {creation_datetime}")
        
    except Exception as e:
        print(f"    ⚠️  Erro ao ajustar timestamps: {e}")

def convert_image_to_webp(input_path, output_path, quality=80):
    """
    Converte uma imagem de qualquer formato suportado para WebP preservando metadados
    
    Args:
        input_path (str): Caminho da imagem original
        output_path (str): Caminho da imagem convertida
        quality (int): Qualidade da compressão (0-100, padrão 80)
    """
    try:
        # Extrai todos os metadados primeiro
        metadata = extract_all_metadata(input_path)
        
        # Extrai data/hora de criação
        creation_datetime = get_creation_datetime_from_exif(metadata['exif'])
        
        with Image.open(input_path) as img:
            # Converte para RGB se necessário, preservando transparência quando possível
            if img.mode in ('RGBA', 'LA'):
                converted_img = img.convert('RGBA')
            elif img.mode == 'P':
                if 'transparency' in img.info:
                    converted_img = img.convert('RGBA')
                else:
                    converted_img = img.convert('RGB')
            elif img.mode not in ('RGB', 'RGBA'):
                converted_img = img.convert('RGB')
            else:
                converted_img = img
            
            # Prepara argumentos para salvar
            save_kwargs = {
                'format': 'WebP',
                'quality': quality,
                'optimize': True,
                'method': 6  # Melhor compressão
            }
            
            # Adiciona perfil ICC se disponível
            if metadata['icc_profile']:
                save_kwargs['icc_profile'] = metadata['icc_profile']
                print(f"    🎨 Perfil de cor ICC preservado")
            
            # Adiciona EXIF limpo se disponível
            if metadata['exif']:
                try:
                    # Converte EXIF para bytes usando dados limpos
                    exif_bytes = piexif.dump(metadata['exif'])
                    save_kwargs['exif'] = exif_bytes
                    print(f"    📋 Metadados EXIF preservados")
                except Exception as e:
                    print(f"    ⚠️  Erro ao preparar EXIF: {e}")
            
            # Salva a imagem
            converted_img.save(output_path, **save_kwargs)
            
            # Ajusta timestamps do arquivo para corresponder à data da foto
            if creation_datetime:
                set_file_timestamps(output_path, creation_datetime)
            
            # Salva backup dos metadados em JSON separado
            save_metadata_backup(input_path, output_path, metadata, creation_datetime)
            
            return True
            
    except Exception as e:
        print(f"Erro ao converter {input_path}: {e}")
        return False

def convert_bytes_for_json(obj):
    """
    Converte recursivamente objetos bytes para string para serialização JSON
    
    Args:
        obj: Objeto a ser convertido
        
    Returns:
        Objeto convertido compatível com JSON
    """
    if isinstance(obj, bytes):
        try:
            # Tenta decodificar como UTF-8
            return obj.decode('utf-8')
        except UnicodeDecodeError:
            # Se falhar, retorna representação hexadecimal
            return f"<bytes:{len(obj)}:{obj.hex()[:50]}{'...' if len(obj.hex()) > 50 else ''}>"
    elif isinstance(obj, dict):
        return {str(k): convert_bytes_for_json(v) for k, v in obj.items()}
    elif isinstance(obj, (list, tuple)):
        return [convert_bytes_for_json(item) for item in obj]
    elif isinstance(obj, (int, float, str, bool)) or obj is None:
        return obj
    else:
        # Para outros tipos, converte para string
        return str(obj)

def save_metadata_backup(original_path, webp_path, metadata, creation_datetime):
    """
    Salva um backup dos metadados em arquivo JSON separado
    """
    try:
        # Cria nome do arquivo de backup
        base_name = os.path.splitext(webp_path)[0]
        backup_path = f"{base_name}_metadata.json"
        
        # Extrai informações importantes do EXIF
        camera_info = {}
        technical_info = {}
        
        if metadata['exif']:
            # Informações da câmera do IFD 0th
            if '0th' in metadata['exif']:
                exif_0th = metadata['exif']['0th']
                camera_tags = {
                    piexif.ImageIFD.Make: 'camera_make',
                    piexif.ImageIFD.Model: 'camera_model',
                    piexif.ImageIFD.Software: 'software',
                    piexif.ImageIFD.DateTime: 'datetime_modified'
                }
                
                for tag_id, key in camera_tags.items():
                    if tag_id in exif_0th:
                        value = exif_0th[tag_id]
                        if isinstance(value, bytes):
                            try:
                                value = value.decode('utf-8', errors='ignore').strip()
                            except:
                                continue
                        camera_info[key] = value
            
            # Informações técnicas do IFD Exif
            if 'Exif' in metadata['exif']:
                exif_data = metadata['exif']['Exif']
                tech_tags = {
                    piexif.ExifIFD.DateTimeOriginal: 'datetime_original',
                    piexif.ExifIFD.DateTimeDigitized: 'datetime_digitized',
                    piexif.ExifIFD.ExposureTime: 'exposure_time',
                    piexif.ExifIFD.FNumber: 'aperture',
                    piexif.ExifIFD.ISOSpeedRatings: 'iso',
                    piexif.ExifIFD.FocalLength: 'focal_length'
                }
                
                for tag_id, key in tech_tags.items():
                    if tag_id in exif_data:
                        value = exif_data[tag_id]
                        if isinstance(value, bytes):
                            try:
                                value = value.decode('utf-8', errors='ignore').strip()
                            except:
                                continue
                        elif isinstance(value, tuple) and len(value) == 2:
                            # Para frações (como tempo de exposição)
                            if value[1] != 0:
                                value = f"{value[0]}/{value[1]}"
                            else:
                                value = str(value[0])
                        technical_info[key] = value
        
        # Prepara dados para JSON
        json_metadata = {
            'original_file': os.path.basename(original_path),
            'webp_file': os.path.basename(webp_path),
            'conversion_date': datetime.now().isoformat(),
            'photo_datetime': creation_datetime,
            'camera_info': camera_info,
            'technical_info': technical_info,
            'has_exif': metadata['exif'] is not None,
            'has_icc_profile': metadata['icc_profile'] is not None,
            'has_xmp': metadata['xmp'] is not None,
            'other_info': convert_bytes_for_json(metadata['other_info'])
        }
        
        # Informações sobre perfil ICC
        if metadata['icc_profile']:
            json_metadata['icc_profile_info'] = {
                'size_bytes': len(metadata['icc_profile']),
                'preview': metadata['icc_profile'][:50].hex() if len(metadata['icc_profile']) > 50 else metadata['icc_profile'].hex()
            }
        
        # Informações sobre XMP
        if metadata['xmp']:
            json_metadata['xmp_info'] = {
                'type': type(metadata['xmp']).__name__,
                'size': len(metadata['xmp']) if hasattr(metadata['xmp'], '__len__') else 'unknown',
                'preview': convert_bytes_for_json(metadata['xmp'][:200] if hasattr(metadata['xmp'], '__getitem__') else str(metadata['xmp'])[:200])
            }
        
        # Salva o arquivo JSON
        with open(backup_path, 'w', encoding='utf-8') as f:
            json.dump(json_metadata, f, indent=2, ensure_ascii=False, default=str)
            
        print(f"    💾 Backup de metadados salvo: {os.path.basename(backup_path)}")
        
    except Exception as e:
        print(f"    ⚠️  Erro ao salvar backup: {e}")
        # Tenta salvar versão simplificada
        try:
            simplified_backup = {
                'original_file': os.path.basename(original_path),
                'webp_file': os.path.basename(webp_path),
                'conversion_date': datetime.now().isoformat(),
                'photo_datetime': creation_datetime,
                'error': f"Erro ao salvar metadados completos: {e}",
                'has_exif': metadata['exif'] is not None,
                'has_icc_profile': metadata['icc_profile'] is not None,
                'metadata_keys': list(metadata['other_info'].keys()) if metadata['other_info'] else []
            }
            
            backup_path_simple = f"{os.path.splitext(webp_path)[0]}_metadata_simple.json"
            with open(backup_path_simple, 'w', encoding='utf-8') as f:
                json.dump(simplified_backup, f, indent=2, ensure_ascii=False)
            print(f"    💾 Backup simplificado salvo: {os.path.basename(backup_path_simple)}")
            
        except Exception as e2:
            print(f"    ❌ Falha total ao salvar backup: {e2}")

def display_metadata_info(image_path):
    """
    Exibe informações sobre os metadados de uma imagem
    
    Args:
        image_path (str): Caminho da imagem
    """
    try:
        metadata = extract_all_metadata(image_path)
        print(f"  📊 Metadados encontrados em {os.path.basename(image_path)}:")
        
        # EXIF data
        if metadata['exif']:
            exif_count = sum(len(ifd) if isinstance(ifd, dict) else 1 for ifd in metadata['exif'].values())
            print(f"    • EXIF: {exif_count} campo(s)")
            
            # Data/hora da foto
            creation_datetime = get_creation_datetime_from_exif(metadata['exif'])
            if creation_datetime:
                print(f"      - Data da foto: {creation_datetime}")
            
            # Mostra alguns campos importantes do EXIF
            if '0th' in metadata['exif']:
                exif_0th = metadata['exif']['0th']
                important_tags = {
                    piexif.ImageIFD.Make: 'Fabricante',
                    piexif.ImageIFD.Model: 'Modelo',
                    piexif.ImageIFD.Software: 'Software'
                }
                
                for tag_id, tag_name in important_tags.items():
                    if tag_id in exif_0th:
                        value = exif_0th[tag_id]
                        if isinstance(value, bytes):
                            value = value.decode('utf-8', errors='ignore')
                        print(f"      - {tag_name}: {value}")
        
        # Outros metadados
        if metadata['other_info']:
            print(f"    • Outros metadados: {len(metadata['other_info'])} campo(s)")
            for key, value in list(metadata['other_info'].items())[:3]:
                print(f"      - {key}: {value}")
        
        # Perfil ICC
        if metadata['icc_profile']:
            print(f"    • Perfil de cor ICC: Presente ({len(metadata['icc_profile'])} bytes)")
            
    except Exception as e:
        print(f"  ⚠️  Erro ao ler metadados: {e}")

def main():
    # Verifica se piexif está instalado
    try:
        import piexif
    except ImportError:
        print("❌ Erro: A biblioteca 'piexif' não está instalada.")
        print("Para instalar, execute: pip install piexif")
        print("Ou: pip install Pillow piexif")
        return
    
    # Obtém o diretório atual onde o script está rodando
    current_dir = os.getcwd()
    
    # Pergunta se o usuário quer ver detalhes dos metadados
    show_metadata = input("Deseja ver detalhes dos metadados durante a conversão? (s/n): ").lower() in ['s', 'sim', 'y', 'yes']
    print()
    
    # Padrões de arquivos de imagem suportados (case-insensitive)
    image_patterns = [
        '*.jpg', '*.jpeg', '*.JPG', '*.JPEG',
        '*.png', '*.PNG',
        '*.bmp', '*.BMP',
        '*.tiff', '*.tif', '*.TIFF', '*.TIF',
        '*.gif', '*.GIF',
        '*.ico', '*.ICO',
        '*.webp', '*.WEBP'
    ]
    
    # Encontra todos os arquivos de imagem
    image_files = []
    for pattern in image_patterns:
        image_files.extend(glob.glob(os.path.join(current_dir, pattern)))
    
    if not image_files:
        print("Nenhum arquivo de imagem encontrado na pasta atual.")
        print("Formatos suportados: JPG, JPEG, PNG, BMP, TIFF, GIF, ICO, WEBP")
        return
    
    print(f"Encontrados {len(image_files)} arquivo(s) de imagem para converter.")
    print(f"Diretório: {current_dir}")
    print("-" * 50)
    
    converted_count = 0
    failed_count = 0
    skipped_count = 0
    
    for image_file in image_files:
        # Gera o nome do arquivo WebP
        base_name = os.path.splitext(os.path.basename(image_file))[0]
        webp_file = os.path.join(current_dir, f"{base_name}.webp")
        
        # Pula se o arquivo já é WebP e tem o mesmo nome de saída
        if image_file.lower().endswith('.webp') and image_file == webp_file:
            print(f"Pulando: {os.path.basename(image_file)} (já é WebP)")
            skipped_count += 1
            continue
            
        print(f"Convertendo: {os.path.basename(image_file)} -> {base_name}.webp")
        
        # Mostra metadados se solicitado
        if show_metadata:
            display_metadata_info(image_file)
        
        # Verifica se o arquivo WebP já existe
        if os.path.exists(webp_file):
            resposta = input(f"O arquivo {base_name}.webp já existe. Sobrescrever? (s/n): ")
            if resposta.lower() not in ['s', 'sim', 'y', 'yes']:
                print("Pulando arquivo...")
                continue
        
        # Converte o arquivo
        if convert_image_to_webp(image_file, webp_file, quality=80):
            # Mostra informações sobre o tamanho dos arquivos
            original_size = os.path.getsize(image_file)
            new_size = os.path.getsize(webp_file)
            reduction = ((original_size - new_size) / original_size) * 100
            
            print(f"  ✓ Convertido com sucesso!")
            print(f"  Tamanho original: {original_size:,} bytes")
            print(f"  Tamanho WebP: {new_size:,} bytes")
            print(f"  Redução: {reduction:.1f}%")
            
            converted_count += 1
        else:
            failed_count += 1
        
        print("-" * 30)
    
    # Resumo final
    print(f"\nResumo da conversão:")
    print(f"Total de arquivos: {len(image_files)}")
    print(f"Convertidos com sucesso: {converted_count}")
    print(f"Pulados (já WebP): {skipped_count}")
    print(f"Falhas: {failed_count}")
    
    if converted_count > 0:
        print(f"\n✓ Conversão concluída! {converted_count} arquivo(s) convertido(s) para WebP.")
        print("📅 Timestamps dos arquivos ajustados para corresponder às datas originais das fotos.")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nConversão interrompida pelo usuário.")
    except Exception as e:
        print(f"\nErro inesperado: {e}")
