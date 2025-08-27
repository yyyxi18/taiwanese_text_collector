# -*- coding: utf-8 -*-
"""
教育部台語辭典最終版爬蟲
Final Version - Manual Operation Style Scraper with Missing Words Report
手動操作風格 + 缺失單字報告
"""

import requests
import time
import json
import re
import pandas as pd
from bs4 import BeautifulSoup
from fake_useragent import UserAgent
from typing import List, Dict, Optional, Tuple
import urllib.parse
from pathlib import Path
import os

class SutianFinalScraper:
    """最終版手動操作風格爬蟲（含缺失單字報告）"""
    
    def __init__(self):
        self.session = requests.Session()
        
        try:
            self.ua = UserAgent()
            user_agent = self.ua.random
        except:
            user_agent = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        
        self.session.headers.update({
            'User-Agent': user_agent,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'zh-TW,zh;q=0.9,en;q=0.8',
            'Referer': 'https://sutian.moe.edu.tw/',
        })
        
        # 禁用SSL警告
        import urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        self.session.verify = False
    
    def search_word_examples(self, word: str) -> List[Dict[str, str]]:
        """步驟1：輸入單字，獲取所有用例"""
        print(f"🔍 輸入單字：{word}")
        
        try:
            # 構建查詢URL（就像在網頁上輸入單字）
            params = {
                'lui': 'tai_ku',  # 用臺灣台語查用例
                'tsha': word
            }
            
            search_url = f"https://sutian.moe.edu.tw/zh-hant/tshiau/?{urllib.parse.urlencode(params)}"
            print(f"   📡 查詢網址：{search_url}")
            
            response = self.session.get(search_url, timeout=15)
            
            if response.status_code == 200:
                examples = self._parse_webpage_examples(response.text, word)
                print(f"   ✅ 找到 {len(examples)} 個可選用例")
                return examples
            else:
                print(f"   ❌ 網頁載入失敗，狀態碼: {response.status_code}")
                return []
                
        except Exception as e:
            print(f"   ❌ 查詢時發生錯誤: {e}")
            return []
    
    def _parse_webpage_examples(self, html: str, word: str) -> List[Dict[str, str]]:
        """解析網頁，提取所有用例（如同瀏覽網頁）"""
        examples = []
        
        try:
            soup = BeautifulSoup(html, 'html.parser')
            
            # 根據實際網頁結構，查找編號的用例（1. 2. 3. 4.）
            numbered_headers = soup.find_all('h2')
            
            print(f"   📋 網頁顯示 {len(numbered_headers)} 個用例選項")
            
            for i, h2_tag in enumerate(numbered_headers, 1):
                try:
                    example_data = self._extract_single_example(h2_tag, word, i)
                    if example_data:
                        examples.append(example_data)
                        print(f"      {i}. {example_data['taiwanese_sentence'][:30]}...")
                    else:
                        print(f"      {i}. 無效用例")
                        
                except Exception as e:
                    print(f"      {i}. 解析錯誤: {e}")
                    continue
            
            return examples
            
        except Exception as e:
            print(f"   ❌ 網頁解析失敗: {e}")
            return []
    
    def _extract_single_example(self, h2_tag, word: str, index: int) -> Optional[Dict[str, str]]:
        """擷取單個用例的三要素：台語例句、台羅拼音、中文翻譯"""
        try:
            # 1. 擷取台語例句（h2標籤文字，去掉編號）
            h2_text = h2_tag.get_text(strip=True)
            taiwanese_sentence = re.sub(r'^\d+\.\s*', '', h2_text).strip()
            
            if not taiwanese_sentence or len(taiwanese_sentence) < 5:
                return None
            
            # 2. 收集h2後的內容來找台羅拼音和中文翻譯
            content_parts = []
            current = h2_tag
            
            # 收集相關的後續內容
            for _ in range(15):  # 限制搜尋範圍
                if current.next_sibling:
                    current = current.next_sibling
                    
                    # 遇到下一個編號就停止
                    if (hasattr(current, 'name') and current.name == 'h2' and 
                        re.match(r'^\d+\.\s*', current.get_text(strip=True))):
                        break
                    
                    if hasattr(current, 'get_text'):
                        text = current.get_text(strip=True)
                        if text:
                            content_parts.append(text)
                    elif isinstance(current, str) and current.strip():
                        content_parts.append(current.strip())
                else:
                    break
            
            full_content = '\n'.join(content_parts)
            
            # 3. 擷取台羅拼音（完整版）
            tailo_pronunciation = self._extract_tailo_carefully(full_content)
            
            # 4. 擷取中文翻譯（從括號中）
            chinese_translation = self._extract_chinese_carefully(full_content)
            
            # 5. 擷取來源詞目
            source_word = self._extract_source_carefully(full_content)
            
            # 只有三要素都存在才算有效用例
            if taiwanese_sentence and (tailo_pronunciation or chinese_translation):
                return {
                    'index': index,
                    'word': word,
                    'taiwanese_sentence': taiwanese_sentence,
                    'tailo_pronunciation': tailo_pronunciation,
                    'chinese_translation': chinese_translation,
                    'source_word': source_word or word,
                    'source': '教育部臺灣台語常用詞辭典'
                }
            
            return None
            
        except Exception as e:
            print(f"      擷取失敗：{e}")
            return None
    
    def _extract_tailo_carefully(self, content: str) -> str:
        """仔細擷取台羅拼音（避免截斷）"""
        if not content:
            return ''
        
        # 移除干擾文字
        cleaned = re.sub(r'播放用例[^。]*', '', content)
        cleaned = re.sub(r'來源詞目[^。]*', '', cleaned)
        
        # 尋找台羅拼音模式
        lines = cleaned.split('\n')
        
        best_tailo = ''
        max_score = 0
        
        for line in lines:
            line = line.strip()
            if len(line) < 10:
                continue
                
            score = self._score_tailo_line(line)
            if score > max_score:
                best_tailo = line
                max_score = score
        
        if best_tailo:
            best_tailo = self._clean_tailo_carefully(best_tailo)
        
        return best_tailo
    
    def _score_tailo_line(self, line: str) -> float:
        """評分台羅拼音行的可能性"""
        score = 0
        
        tailo_chars = 'âêîôûāēīōūǎěǐǒǔàèìòù'
        special_count = sum(1 for char in line if char in tailo_chars)
        score += special_count * 3
        
        latin_count = sum(1 for char in line if char.isalpha())
        total_chars = len(re.sub(r'\s+', '', line))
        if total_chars > 0:
            latin_ratio = latin_count / total_chars
            if latin_ratio > 0.6:
                score += 10
        
        chinese_count = sum(1 for char in line if '\u4e00' <= char <= '\u9fff')
        if chinese_count == 0:
            score += 5
        else:
            score -= chinese_count
        
        bad_words = ['播放', '搜尋', '辭典', '來源', 'http']
        for bad_word in bad_words:
            if bad_word in line:
                score -= 10
        
        return score
    
    def _clean_tailo_carefully(self, tailo: str) -> str:
        """仔細清理台羅拼音"""
        tailo = re.sub(r'^播放用例', '', tailo)
        tailo = re.sub(r'播放.*$', '', tailo)
        tailo = re.sub(r'來源.*$', '', tailo)
        tailo = re.sub(r'^[.,;:!?()\'"]+|[.,;:!?()\'"]+$', '', tailo)
        tailo = re.sub(r'\s+', ' ', tailo).strip()
        return tailo
    
    def _extract_chinese_carefully(self, content: str) -> str:
        """仔細擷取中文翻譯"""
        if not content:
            return ''
        
        bracket_patterns = [
            r'[\(（]([^)）]{5,})[\)）]',
        ]
        
        for pattern in bracket_patterns:
            matches = re.findall(pattern, content)
            for match in matches:
                if (len(match) > 3 and 
                    self._is_valid_chinese(match) and
                    '播放' not in match and '搜尋' not in match):
                    return match.strip()
        
        return ''
    
    def _is_valid_chinese(self, text: str) -> bool:
        """檢查是否為有效的中文文字"""
        if not text:
            return False
        
        chinese_count = sum(1 for char in text if '\u4e00' <= char <= '\u9fff')
        total_count = len(text)
        
        return chinese_count / total_count > 0.5 if total_count > 0 else False
    
    def _extract_source_carefully(self, content: str) -> str:
        """仔細擷取來源詞目"""
        source_patterns = [
            r'來源詞目[：:\s]*([^\s\n]+)',
        ]
        
        for pattern in source_patterns:
            match = re.search(pattern, content)
            if match:
                source = match.group(1).strip()
                source = re.sub(r'播放.*$', '', source)
                return source.strip()
        
        return ''
    
    def select_best_example(self, examples: List[Dict[str, str]]) -> Optional[Dict[str, str]]:
        """步驟2：從用例中選擇最佳的一個（模擬人工選擇）"""
        if not examples:
            return None
        
        if len(examples) == 1:
            print(f"   📌 自動選擇唯一用例")
            return examples[0]
        
        def rate_example(example):
            score = 0
            
            if example.get('tailo_pronunciation'):
                score += 30
                score += len(example['tailo_pronunciation']) * 0.5
            
            if example.get('chinese_translation'):
                score += 20
            
            taiwanese = example.get('taiwanese_sentence', '')
            if taiwanese:
                score += len(taiwanese) * 0.3
                if any(punct in taiwanese for punct in ['。', '！', '？']):
                    score += 10
            
            return score
        
        examples.sort(key=rate_example, reverse=True)
        best = examples[0]
        
        print(f"   📌 選擇最佳用例：{best['taiwanese_sentence'][:30]}...")
        return best
    
    def save_extracted_data(self, word: str, example: Dict[str, str]) -> Dict[str, str]:
        """步驟4：儲存管理擷取的三要素"""
        if not example:
            return None
        
        record = {
            'word': word,
            'taiwanese_sentence': example.get('taiwanese_sentence', ''),
            'tailo_pronunciation': example.get('tailo_pronunciation', ''),
            'chinese_translation': example.get('chinese_translation', ''),
            'source_word': example.get('source_word', ''),
            'extraction_time': time.strftime('%Y-%m-%d %H:%M:%S'),
            'source': example.get('source', ''),
            'data_quality': self._assess_data_quality(example)
        }
        
        return record
    
    def _assess_data_quality(self, example: Dict[str, str]) -> str:
        """評估資料品質"""
        has_tailo = bool(example.get('tailo_pronunciation'))
        has_chinese = bool(example.get('chinese_translation'))
        has_taiwanese = bool(example.get('taiwanese_sentence'))
        
        if has_tailo and has_chinese and has_taiwanese:
            return '完整'
        elif (has_tailo and has_taiwanese) or (has_chinese and has_taiwanese):
            return '良好'
        elif has_taiwanese:
            return '基本'
        else:
            return '不完整'
    
    def process_word_manual_style(self, word: str) -> Tuple[Optional[Dict[str, str]], str]:
        """完整模擬手動操作流程，返回結果和狀態"""
        print(f"\n🎯 手動操作流程：{word}")
        print("-" * 50)
        
        # 步驟1：輸入單字，獲取用例
        examples = self.search_word_examples(word)
        if not examples:
            print("   ❌ 沒有找到可用的用例")
            return None, "無用例"
        
        # 步驟2：選擇最佳用例
        selected = self.select_best_example(examples)
        if not selected:
            print("   ❌ 無法選擇有效用例")
            return None, "無效用例"
        
        # 步驟3：擷取三要素並顯示
        print(f"   📝 擷取結果：")
        print(f"      台語：{selected.get('taiwanese_sentence', '無')}")
        print(f"      台羅：{selected.get('tailo_pronunciation', '無')}")
        print(f"      中文：{selected.get('chinese_translation', '無')}")
        
        # 步驟4：儲存管理
        record = self.save_extracted_data(word, selected)
        print(f"   💾 資料品質：{record.get('data_quality', '未知')}")
        
        return record, "成功"
    
    def process_wordlist_with_missing_report(self, wordlist: List[str]) -> Tuple[List[Dict[str, str]], List[str]]:
        """批次處理單字列表並產生缺失報告"""
        print(f"\n📚 批次手動操作模式（含缺失報告）")
        print(f"🎯 處理 {len(wordlist)} 個單字")
        print("=" * 60)
        
        successful_results = []
        missing_words = []
        
        for i, word in enumerate(wordlist, 1):
            print(f"\n進度 {i:2d}/{len(wordlist)}")
            
            try:
                record, status = self.process_word_manual_style(word)
                if record:
                    successful_results.append(record)
                    print(f"   ✅ 成功擷取")
                else:
                    missing_words.append({
                        'word': word,
                        'reason': status,
                        'index': i
                    })
                    print(f"   ❌ 擷取失敗：{status}")
                
                # 模擬人工操作間隔
                if i < len(wordlist):
                    time.sleep(2.5)
                    
            except Exception as e:
                missing_words.append({
                    'word': word,
                    'reason': f"錯誤: {e}",
                    'index': i
                })
                print(f"   ❌ 處理錯誤: {e}")
                continue
        
        return successful_results, missing_words
    
    def save_results_with_missing_report(self, results: List[Dict], missing_words: List[Dict], title: str = "最終結果") -> Dict[str, str]:
        """儲存結果並包含缺失單字報告"""
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        safe_title = re.sub(r'[\\/:*?"<>|]', '_', title)
        
        # 建立輸出目錄
        output_dir = f"final_{safe_title}"
        os.makedirs(output_dir, exist_ok=True)
        
        total_words = len(results) + len(missing_words)
        
        # 儲存主要結果JSON
        json_file = f"{output_dir}/{safe_title}_final_{timestamp}.json"
        json_data = {
            'metadata': {
                'scraper_type': '最終版手動操作風格爬蟲',
                'operation_flow': '輸入單字 → 選擇用例 → 擷取三要素 → 儲存管理',
                'source_url': 'https://sutian.moe.edu.tw/zh-hant/tshiau/',
                'extraction_date': timestamp,
                'statistics': {
                    'total_words': total_words,
                    'successful_extractions': len(results),
                    'missing_words': len(missing_words),
                    'success_rate': f"{len(results)/total_words*100:.1f}%" if total_words > 0 else "0%",
                    'quality_stats': self._calculate_quality_stats(results)
                }
            },
            'successful_records': results,
            'missing_words': missing_words
        }
        
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(json_data, f, ensure_ascii=False, indent=2)
        
        # 儲存成功記錄CSV
        csv_file = f"{output_dir}/{safe_title}_successful_{timestamp}.csv"
        if results:
            csv_data = []
            
            for record in results:
                csv_data.append({
                    '單字': record['word'],
                    '台語例句': record['taiwanese_sentence'],
                    '台羅拼音': record['tailo_pronunciation'],
                    '中文翻譯': record['chinese_translation'],
                    '來源詞目': record['source_word'],
                    '資料品質': record['data_quality'],
                    '擷取時間': record['extraction_time'],
                    '資料來源': record['source']
                })
            
            df = pd.DataFrame(csv_data)
            quality_order = {'完整': 4, '良好': 3, '基本': 2, '不完整': 1}
            df['品質分數'] = df['資料品質'].map(quality_order).fillna(0)
            df = df.sort_values(['品質分數', '單字'], ascending=[False, True])
            df = df.drop('品質分數', axis=1)
            df.to_csv(csv_file, index=False, encoding='utf-8-sig')
        
        # 儲存缺失單字CSV
        missing_csv_file = f"{output_dir}/{safe_title}_missing_words_{timestamp}.csv"
        if missing_words:
            missing_df = pd.DataFrame(missing_words)
            missing_df = missing_df.sort_values('index')
            missing_df.to_csv(missing_csv_file, index=False, encoding='utf-8-sig')
        
        # 儲存完整報告TXT
        txt_file = f"{output_dir}/{safe_title}_complete_report_{timestamp}.txt"
        with open(txt_file, 'w', encoding='utf-8') as f:
            f.write(f"最終版台語辭典擷取完整報告 - {title}\n")
            f.write("=" * 80 + "\n")
            f.write(f"🎯 操作流程：輸入單字 → 選擇用例 → 擷取三要素 → 儲存管理\n")
            f.write(f"📊 完整統計：\n")
            f.write(f"   - 總計單字：{total_words} 個\n")
            f.write(f"   - 成功擷取：{len(results)} 個\n")
            f.write(f"   - 缺失單字：{len(missing_words)} 個\n")
            f.write(f"   - 成功率：{len(results)/total_words*100:.1f}%\n" if total_words > 0 else "   - 成功率：0%\n")
            f.write(f"⏰ 擷取時間：{timestamp}\n\n")
            
            # 成功擷取的結果
            if results:
                complete_records = [r for r in results if r['data_quality'] == '完整']
                good_records = [r for r in results if r['data_quality'] == '良好']
                basic_records = [r for r in results if r['data_quality'] == '基本']
                
                if complete_records:
                    f.write("🌟 完整擷取（台語+台羅+中文）:\n")
                    f.write("-" * 60 + "\n")
                    for i, record in enumerate(complete_records, 1):
                        f.write(f"{i:2d}. {record['word']}\n")
                        f.write(f"    台語：{record['taiwanese_sentence']}\n")
                        f.write(f"    台羅：{record['tailo_pronunciation']}\n")
                        f.write(f"    中文：{record['chinese_translation']}\n")
                        if record['source_word'] != record['word']:
                            f.write(f"    來源：{record['source_word']}\n")
                        f.write("\n")
                
                if good_records:
                    f.write("📝 良好擷取:\n")
                    f.write("-" * 60 + "\n")
                    for i, record in enumerate(good_records, 1):
                        f.write(f"{i:2d}. {record['word']}\n")
                        f.write(f"    台語：{record['taiwanese_sentence']}\n")
                        if record['tailo_pronunciation']:
                            f.write(f"    台羅：{record['tailo_pronunciation']}\n")
                        if record['chinese_translation']:
                            f.write(f"    中文：{record['chinese_translation']}\n")
                        f.write("\n")
                
                if basic_records:
                    f.write("📄 基本擷取:\n")
                    f.write("-" * 60 + "\n")
                    for i, record in enumerate(basic_records, 1):
                        f.write(f"{i:2d}. {record['word']}\n")
                        f.write(f"    台語：{record['taiwanese_sentence']}\n")
                        f.write("\n")
            
            # 缺失單字報告
            if missing_words:
                f.write("❌ 缺失單字報告:\n")
                f.write("=" * 60 + "\n")
                f.write(f"以下 {len(missing_words)} 個單字沒有找到可用的例句：\n\n")
                
                # 按原因分組
                reasons = {}
                for missing in missing_words:
                    reason = missing['reason']
                    if reason not in reasons:
                        reasons[reason] = []
                    reasons[reason].append(missing['word'])
                
                for reason, words in reasons.items():
                    f.write(f"📋 {reason} ({len(words)}個):\n")
                    for i, word in enumerate(words, 1):
                        if i % 10 == 1:
                            f.write("   ")
                        f.write(f"{word:<8}")
                        if i % 10 == 0:
                            f.write("\n")
                    if len(words) % 10 != 0:
                        f.write("\n")
                    f.write("\n")
                
                f.write("💡 建議：\n")
                f.write("   1. 這些單字可能在教育部辭典中沒有用例\n")
                f.write("   2. 可以嘗試其他台語辭典或資源\n")
                f.write("   3. 或者手動查詢相關的同義詞\n")
        
        print(f"\n💾 最終結果已儲存:")
        print(f"   📊 完整JSON: {json_file}")
        if results:
            print(f"   📋 成功CSV: {csv_file}")
        if missing_words:
            print(f"   ❌ 缺失CSV: {missing_csv_file}")
        print(f"   📖 完整報告: {txt_file}")
        
        # 顯示缺失摘要
        if missing_words:
            print(f"\n❌ 缺失單字摘要：")
            reasons = {}
            for missing in missing_words:
                reason = missing['reason']
                if reason not in reasons:
                    reasons[reason] = []
                reasons[reason].append(missing['word'])
            
            for reason, words in reasons.items():
                print(f"   {reason}: {len(words)}個")
                sample_words = words[:5]
                print(f"     如：{', '.join(sample_words)}{'...' if len(words) > 5 else ''}")
        
        return {
            'json_file': json_file,
            'csv_file': csv_file if results else None,
            'missing_csv_file': missing_csv_file if missing_words else None,
            'txt_file': txt_file,
            'output_dir': output_dir
        }
    
    def _calculate_quality_stats(self, results: List[Dict]) -> Dict[str, int]:
        """計算品質統計"""
        stats = {'完整': 0, '良好': 0, '基本': 0, '不完整': 0}
        
        for record in results:
            quality = record.get('data_quality', '不完整')
            if quality in stats:
                stats[quality] += 1
        
        return stats
    
    def cleanup(self):
        """清理資源"""
        if hasattr(self, 'session'):
            self.session.close()

def main():
    """最終版爬蟲主程式"""
    scraper = SutianFinalScraper()
    
    try:
        print("🏆 教育部台語辭典最終版爬蟲")
        print("=" * 60)
        print("📋 特色：手動操作風格 + 缺失單字報告")
        print("🎯 功能：完整追蹤哪些單字沒有找到例句")
        print("🏛️ 資料來源：教育部臺灣台語常用詞辭典\n")
        
        while True:
            print("請選擇操作模式：")
            print("1. 單字測試（手動輸入）")
            print("2. 工作表批次處理（含缺失報告）")
            print("3. 自定義單字列表（含缺失報告）")
            print("0. 退出")
            
            choice = input("\n請輸入選項 (0-3): ").strip()
            
            if choice == '0':
                print("👋 感謝使用最終版爬蟲！")
                break
                
            elif choice == '1':
                # 單字測試
                word = input("請輸入要測試的台語單字：").strip()
                if word:
                    result, status = scraper.process_word_manual_style(word)
                    if result:
                        print(f"\n✅ 成功擷取「{word}」的資料")
                    else:
                        print(f"\n❌ 無法擷取「{word}」的資料，原因：{status}")
                else:
                    print("❌ 請輸入有效的單字")
                    
            elif choice == '2':
                # 工作表處理
                excel_file = "臺語詞彙0720.xlsx"
                try:
                    excel_obj = pd.ExcelFile(excel_file)
                    worksheets = [name for name in excel_obj.sheet_names if name != "工作表分類清單"]
                    
                    print(f"\n📚 可用工作表：")
                    for i, ws in enumerate(worksheets, 1):
                        print(f"  {i:2d}. {ws}")
                    
                    ws_choice = input(f"\n請選擇工作表編號 (1-{len(worksheets)}): ").strip()
                    ws_index = int(ws_choice) - 1
                    
                    if 0 <= ws_index < len(worksheets):
                        selected_ws = worksheets[ws_index]
                        
                        # 提取單字
                        df = pd.read_excel(excel_file, sheet_name=selected_ws)
                        words = []
                        
                        for column in df.columns:
                            column_words = df[column].astype(str).tolist()
                            for word in column_words:
                                word = word.strip()
                                if (word and word != 'nan' and 
                                    not word.isdigit() and 
                                    len(word) > 1 and
                                    any('\u4e00' <= char <= '\u9fff' for char in word)):
                                    
                                    cleaned_word = re.sub(r'^\d+\.?\s*', '', word)
                                    cleaned_word = re.sub(r'\([^)]*\)', '', cleaned_word)
                                    cleaned_word = cleaned_word.strip()
                                    
                                    if len(cleaned_word) > 1 and cleaned_word not in ['其他', '備註', '說明', '類別']:
                                        words.append(cleaned_word)
                        
                        # 去重
                        words = list(set(words))
                        print(f"\n📝 找到 {len(words)} 個單字")
                        
                        # 詢問是否繼續
                        confirm = input(f"是否開始處理？(y/n): ").lower().strip()
                        if confirm == 'y':
                            results, missing_words = scraper.process_wordlist_with_missing_report(words)
                            
                            saved = scraper.save_results_with_missing_report(results, missing_words, selected_ws)
                            if saved:
                                print(f"\n🎉 工作表「{selected_ws}」處理完成！")
                                print(f"📁 結果儲存在：{saved['output_dir']}")
                        else:
                            print("👋 已取消操作")
                    else:
                        print("❌ 無效的工作表選擇")
                        
                except Exception as e:
                    print(f"❌ 處理工作表失敗: {e}")
                    
            elif choice == '3':
                # 自定義列表
                print("請輸入台語單字（一行一個，輸入空行結束）：")
                words = []
                while True:
                    word = input().strip()
                    if not word:
                        break
                    words.append(word)
                
                if words:
                    results, missing_words = scraper.process_wordlist_with_missing_report(words)
                    saved = scraper.save_results_with_missing_report(results, missing_words, "自定義列表")
                    if saved:
                        print(f"\n🎉 自定義列表處理完成！")
                        print(f"📁 結果儲存在：{saved['output_dir']}")
                else:
                    print("❌ 沒有輸入有效的單字")
                    
            else:
                print("❌ 無效選項")
    
    finally:
        scraper.cleanup()

if __name__ == "__main__":
    main()

