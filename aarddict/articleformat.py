"""
This file is part of AardDict (http://code.google.com/p/aarddict) - 
a dictionary for Nokia Internet Tablets. 

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation version 3 of the License.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.

Copyright (C) 2008  Jeremy Mortis and Igor Tkach
"""

import threading
import time
 
import gobject 
import gtk
import pango

import simplejson 
import article

def to_article(raw_article):
    try:
        t0 = time.time()
        text, tag_list = simplejson.loads(raw_article)
        print 'Loaded json in ', time.time() - t0, ' s'
    except Exception, e:
        print e, 'was trying to load article from string:\n%s' % raw_article[:10]
        text = raw_article
        tags = []
    else:
        tags = [article.Tag(name, start, end, attrs) 
                for name, start, end, attrs in tag_list]            
    return article.Article(text=text, tags=tags)


class FormattingStoppedException(Exception):
    def __init__(self):
        self.value = "Formatting stopped"
    def __str__(self):
        return repr(self.value)   

class ArticleFormat:
    class Worker(threading.Thread):        
        def __init__(self, formatter, dict, word, article, article_view):
            super(ArticleFormat.Worker, self).__init__()
            self.dict = dict
            self.word = word
            self.article = article
            self.article_view = article_view
            self.formatter = formatter
            self.stopped = True

        def run(self):
            self.stopped = False
            text_buffer = self.formatter.create_tagged_text_buffer(self.dict, self.article, self.article_view)
            if not self.stopped:
                gobject.idle_add(self.article_view.set_buffer, text_buffer)
                self.formatter.workers.pop(self.dict, None)
        
        def stop(self):
            self.stopped = True
            
    def __init__(self, internal_link_callback, external_link_callback):
        self.internal_link_callback = internal_link_callback
        self.external_link_callback = external_link_callback
        self.workers = {}
   
    def stop(self):
        [worker.stop() for worker in self.workers.itervalues()]
        self.workers.clear()
   
    def apply(self, dict, word, article, article_view):
        current_worker = self.workers.pop(dict, None)
        if current_worker:
            current_worker.stop()
        self.article_view = article_view
        loading = self.create_article_text_buffer()
        loading.set_text("Loading...")
        article_view.set_buffer(loading)
        self.workers[dict] = self.Worker(self, dict, word, article, article_view)
        self.workers[dict].start()
        
    def create_ref(self, dict, text_buffer, start, end, target):
        ref_tag = text_buffer.create_tag()
        if target.startswith("http://"):
            ref_tag.connect("event", self.external_link_callback , target)
            text_buffer.apply_tag_by_name("url", start, end)
        else:
            ref_tag.connect("event", self.internal_link_callback, target, dict)
            text_buffer.apply_tag_by_name("r", start, end)
        text_buffer.apply_tag(ref_tag, start, end) 
        
    def create_tagged_text_buffer(self, dict, raw_article, article_view):
        text_buffer = self.create_article_text_buffer()
        a = to_article(raw_article)
        text_buffer.set_text(a.text)
        tags = a.tags
        for tag in tags:
            start = text_buffer.get_iter_at_offset(tag.start)
            end = text_buffer.get_iter_at_offset(tag.end)
            if tag.name in ('a', 'iref'):
                self.create_ref(dict, text_buffer, start, end, 
                                str(tag.attributes['href']))
            elif tag.name == 'kref':
                self.create_ref(dict, text_buffer, start, end, 
                                text_buffer.get_text(start, end))                
            elif tag.name == "c":
                if 'c' in tag.attributes:
                    color_code = tag.attributes['c']
                    t = text_buffer.create_tag(None, foreground = color_code)                    
                    text_buffer.apply_tag(t, start, end)
            else:
                text_buffer.apply_tag_by_name(tag.name, start, end)
        return text_buffer
        
    def create_article_text_buffer(self):
        buffer = gtk.TextBuffer()
        buffer.create_tag("b", weight = pango.WEIGHT_BOLD)
        buffer.create_tag("strong", weight = pango.WEIGHT_BOLD)
        buffer.create_tag("small", scale = pango.SCALE_SMALL)
        buffer.create_tag("big", scale = pango.SCALE_LARGE)
        
        buffer.create_tag("h1", 
                          weight = pango.WEIGHT_ULTRABOLD, 
                          scale = pango.SCALE_X_LARGE, 
                          pixels_above_lines = 12, 
                          pixels_below_lines = 6)
        buffer.create_tag("h2", 
                          weight = pango.WEIGHT_BOLD, 
                          scale = pango.SCALE_LARGE, 
                          pixels_above_lines = 6, 
                          pixels_below_lines = 3)        
        buffer.create_tag("h3", 
                          weight = pango.WEIGHT_BOLD, 
                          scale = pango.SCALE_MEDIUM, 
                          pixels_above_lines = 3, 
                          pixels_below_lines = 2)
        buffer.create_tag("h4", 
                          weight = pango.WEIGHT_SEMIBOLD, 
                          scale = pango.SCALE_MEDIUM, 
                          pixels_above_lines = 3, 
                          pixels_below_lines = 2)
        buffer.create_tag("h5", 
                          weight = pango.WEIGHT_SEMIBOLD, 
                          scale = pango.SCALE_MEDIUM, 
                          style = pango.STYLE_ITALIC, 
                          pixels_above_lines = 3, 
                          pixels_below_lines = 2)
        buffer.create_tag("h6", 
                          scale = pango.SCALE_MEDIUM, 
                          underline = pango.UNDERLINE_SINGLE, 
                          pixels_above_lines = 3, 
                          pixels_below_lines = 2)
        
        buffer.create_tag("i", style = pango.STYLE_ITALIC)
        buffer.create_tag("u", underline = True)
        buffer.create_tag("tt", family = 'monospace')        
        
        buffer.create_tag("pos", 
                          style = pango.STYLE_ITALIC, 
                          weight = pango.WEIGHT_SEMIBOLD,
                          foreground = "darkgreen")
        
        buffer.create_tag("r", 
                          underline = pango.UNDERLINE_SINGLE, 
                          foreground = "brown4")
        
        buffer.create_tag("url", 
                          underline = pango.UNDERLINE_SINGLE, 
                          foreground = "steelblue4")
        
        buffer.create_tag("tr", 
                          weight = pango.WEIGHT_BOLD, 
                          foreground = "darkred")
        
        buffer.create_tag("sup", rise = 2, scale = pango.SCALE_XX_SMALL)
        buffer.create_tag("sub", rise = -2, scale = pango.SCALE_XX_SMALL)
        
        buffer.create_tag("blockquote", indent = 6)
        
        'Key phrase'
        buffer.create_tag('k', 
                          weight = pango.WEIGHT_BOLD, 
                          scale = pango.SCALE_LARGE, 
                          pixels_above_lines = 6, 
                          pixels_below_lines = 3)        

        'Direct translation of the key-phrase'
        buffer.create_tag('dtrn')
                
        'Marks the text of an editorial comment'
        buffer.create_tag('co',
                          foreground = "slategray4",
                          scale = pango.SCALE_SMALL)
        
        'Marks the text of an example'
        buffer.create_tag('ex',
                          style = pango.STYLE_ITALIC,
                          family = 'serif',
                          foreground = "darkblue")

        'Marks an abbreviation that is listed in the <abbreviations> section'
        buffer.create_tag('abr',
                          weight = pango.WEIGHT_BOLD,
                          style = pango.STYLE_ITALIC,
                          foreground = "darkred")
        
        'Tag that marks the whole article'
        buffer.create_tag('ar')
        
        return buffer                
