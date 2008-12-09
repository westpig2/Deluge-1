/*
Script: deluge-add.js
    Contains the add torrent window and the torrent creator window.

License:
    General Public License v3

Copyright:
    Damien Churchill (c) 2008 <damoxc@gmail.com>
*/

Deluge.Widgets.AddWindow = new Class({
    Extends: Widgets.Window,
    options: {
        width: 550,
        height: 500,
        title: _('Add Torrents'),
        url: '/template/render/html/window_add_torrent.html'
    },
    
    initialize: function() {
        this.parent();
        this.bound = {
            onLoad: this.onLoad.bindWithEvent(this),
            onAdd: this.onAdd.bindWithEvent(this),
            onCancel: this.onCancel.bindWithEvent(this),
            onTorrentAdded: this.onTorrentAdded.bindWithEvent(this),
            onTorrentChanged: this.onTorrentChanged.bindWithEvent(this)
        }
        this.addEvent('loaded', this.bound.onLoad);
    },
    
    onLoad: function(e) {
        this.content.id = 'addTorrent';
        this.torrents = this.content.getElement('select');
        this.torrents.addEvent('change', this.bound.onTorrentChanged);
        this.torrentInfo = new Hash();
        this.tabs = new Widgets.Tabs(this.content.getElement('div.moouiTabs'));
        this.filesTab = new Deluge.Widgets.AddTorrent.FilesTab();
        this.tabs.addPage(this.filesTab);
        this.tabs.addPage(new Widgets.TabPage('Options', {
            url: '/template/render/html/add_torrent_options.html'
        }));
        
        this.fileWindow = new Deluge.Widgets.AddTorrent.File();
        this.fileWindow.addEvent('torrentAdded', this.bound.onTorrentAdded);
        this.fileButton = this.content.getElement('button.file');
        this.fileButton.addEvent('click', function(e) {
            this.fileWindow.show();
        }.bindWithEvent(this));
        
        this.urlWindow = new Deluge.Widgets.AddTorrent.Url();
        this.urlWindow.addEvent('torrentAdded', this.bound.onTorrentAdded);     
        this.urlButton = this.content.getElement('button.url');
        this.urlButton.addEvent('click', function(e) {
            this.urlWindow.show();
        }.bindWithEvent(this));
        
        this.content.getElement('button.add').addEvent('click', this.bound.onAdd);
        this.content.getElement('button.cancel').addEvent('click', this.bound.onCancel);
    },
    
    onTorrentAdded: function(torrentInfo) {
        var option = new Element('option');
        option.set('value', torrentInfo['info_hash']);
        var filename = torrentInfo['filename'].split('/');
        filename = filename[filename.length - 1];
        option.set('text', torrentInfo['name'] + ' (' + filename + ')');
        this.torrents.grab(option);
        this.torrentInfo[torrentInfo['info_hash']] = torrentInfo;
    },
    
    onTorrentChanged: function(e) {
        this.filesTab.setTorrent(this.torrentInfo[this.torrents.value]);
    },
    
    onAdd: function(e) {
        torrents = new Array();
        $each(this.torrentInfo, function(torrent) {
            torrents.include({
                path: torrent['filename'],
                options: {}
            });
        }, this);
        Deluge.Client.add_torrents(torrents);
        this.onCancel()
    },
    
    onCancel: function(e) {
        this.hide();
        this.torrents.empty();
        this.torrentInfo.empty();
        this.filesTab.table.empty();
    }
});

Deluge.Widgets.AddTorrent = {}

Deluge.Widgets.AddTorrent.File = new Class({
    Extends: Widgets.Window,
    
    options: {
        width: 400,
        height: 100,
        title: _('From File')
    },
    
    initialize: function() {
        this.parent();
        this.bound = {
            onLoad: this.onLoad.bindWithEvent(this),
            onCancel: this.onCancel.bindWithEvent(this),
            onSubmit: this.onSubmit.bindWithEvent(this),
            onComplete: this.onComplete.bindWithEvent(this),
            onBeforeShow: this.onBeforeShow.bindWithEvent(this),
            onGetInfoSuccess: this.onGetInfoSuccess.bindWithEvent(this)
        };
        this.addEvent('beforeShow', this.bound.onBeforeShow);
    },

    onBeforeShow: function(e) {
        if (this.iframe) this.iframe.destroy();
        this.iframe = new Element('iframe', {
            src: '/template/render/html/window_add_torrent_file.html',
            height: 65,
            width: 390,
            style: {
                background: 'White',
                overflow: 'hidden'
            }
        });
        this.content.grab(this.iframe);
        this.iframe.addEvent('load', this.bound.onLoad);
    },
    
    onLoad: function(e) {
        var body = $(this.iframe.contentDocument.body);
        var form = body.getElement('form');
        var cancelButton = form.getElement('button.cancel');
        cancelButton.addEvent('click', this.bound.onCancel);
        
        var fileInputs = form.getElement('div.fileInputs');
        var fileInput = fileInputs.getElement('input');
        fileInput.set('opacity', 0.000001);
        var fakeFile = fileInputs.getElement('div').getElement('input');
        
        fileInput.addEvent('change', function(e) {
            fakeFile.value = fileInput.value;
        });
        
        form.addEvent('submit', this.bound.onSubmit);
        this.iframe.removeEvent('load', this.bound.onLoad);
    },
    
    onCancel: function(e) {
        this.hide();
    },
    
    onSubmit: function(e) {
        this.iframe.addEvent('load', this.bound.onComplete);
        this.iframe.set('opacity', 0);
    },
    
    onComplete: function(e) {
        filename = $(this.iframe.contentDocument.body).get('text');
        this.hide();
        Deluge.Client.get_torrent_info(filename, {
            onSuccess: this.bound.onGetInfoSuccess
        });
    },
    
    onGetInfoSuccess: function(info) {
        if (info) this.fireEvent('torrentAdded', info);
    }
});

Deluge.Widgets.AddTorrent.Url = new Class({
    Extends: Widgets.Window,
    
    options: {
        width: 300,
        height: 100,
        title: _('From Url')
    },
    
    initialize: function() {
        this.parent();
        this.bound = {
            onOkClick: this.onOkClick.bindWithEvent(this),
            onCancelClick: this.onCancelClick.bindWithEvent(this),
            onDownloadSuccess: this.onDownloadSuccess.bindWithEvent(this),
            onGetInfoSuccess: this.onGetInfoSuccess.bindWithEvent(this)
        };
        
        this.form = new Element('form');
        this.urlInput = new Element('input', {
            type: 'text',
            id: 'urlInput',
            name: 'urlInput'
        });
        this.okButton = new Element('button');
        this.okButton.set('text', _('Ok'));
        this.cancelButton = new Element('button');
        this.cancelButton.set('text', _('Cancel'));
        this.form.grab(new Element('label', {
            for: 'urlInput',
            text: _('Url'),
        }).addClass('fluid'));
        this.form.grab(this.urlInput).grab(new Element('br'));
        this.form.grab(this.okButton).grab(this.cancelButton);
        this.content.grab(this.form);
        
        this.okButton.addEvent('click', this.bound.onOkClick);
        this.cancelButton.addEvent('click', this.bound.onCancelClick);
    },
    
    onOkClick: function(e) {
        e.stop();
        var url = this.urlInput.get('value');
        Deluge.Client.download_torrent_from_url(url, {
            onSuccess: this.bound.onDownloadSuccess
        });
        this.hide();
    },
    
    onCancelClick: function(e) {
        e.stop();
        this.urlInput.set('value', '');
        this.hide();
    },
    
    onDownloadSuccess: function(filename) {
        Deluge.Client.get_torrent_info(filename, {
            onSuccess: this.bound.onGetInfoSuccess
        });
    },
    
    onGetInfoSuccess: function(info) {
        this.fireEvent('torrentAdded', info);
    }
});

Deluge.Widgets.AddTorrent.FilesTab = new Class({
    Extends: Widgets.TabPage,
    
    options: {
        url: '/template/render/html/add_torrent_files.html'
    },
    
    initialize: function() {
        this.addEvent('loaded', this.onLoad.bindWithEvent(this));
        this.parent('Files');
    },
    
    onLoad: function(e) {
        this.table = this.element.getElement('table');    
    },
    
    setTorrent: function(torrent) {
        this.table.empty();
        $each(torrent['files'], function(file) {
            row = new Element('tr');
            new Element('td').inject(row);
            new Element('td').set('text', file['path']).inject(row);
            new Element('td').set('text', file['size'].toBytes()).inject(row);
            this.table.grab(row);
        }, this);
    }
});

Deluge.Widgets.CreateTorrent = new Class({
    Extends: Widgets.Window,
    
    options: {
        width: 400,
        height: 400,
        title: _('Create Torrent'),
        url: '/template/render/html/window_create_torrent.html'
    },
    
    initialize: function() {
        this.parent();
        this.bound = {
            onLoad: this.onLoad.bindWithEvent(this),
            onFileClick: this.onFileClick.bindWithEvent(this),
            onFilesPicked: this.onFilesPicked.bind(this)
        }
        this.addEvent('loaded', this.bound.onLoad);
    },
    
    onLoad: function(e) {
        this.tabs = new Deluge.Widgets.CreateTorrent.Tabs(this.content.getElement('.moouiTabs'));
        this.fileButton = this.content.getElement('button.file');
        this.folderButton = this.content.getElement('button.folder');
        this.content.id = 'createTorrent';
        
        this.fileButton.addEvent('click', this.bound.onFileClick);
    },
    
    onFileClick: function(e) {
        var desktop = google.gears.factory.create('beta.desktop');
        desktop.openFiles(this.onFilesPicked.bind(this));
    },
    
    onFilesPicked: function(files) {
        for (var i = 0; i < files.length; i++) {
            alert(files[i].blob);
        };
    }
});

Deluge.Widgets.CreateTorrent.Tabs = new Class({
    Extends: Widgets.Tabs,
    
    initialize: function(element) {
        this.parent(element);
        this.info = new Deluge.Widgets.CreateTorrent.InfoTab();
        this.trackers = new Deluge.Widgets.CreateTorrent.TrackersTab();
        this.webseeds = new Deluge.Widgets.CreateTorrent.WebseedsTab();
        this.options = new Deluge.Widgets.CreateTorrent.OptionsTab();
        this.addPage(this.info);
        this.addPage(this.trackers);
        this.addPage(this.webseeds);
        this.addPage(this.options);
    }
});

Deluge.Widgets.CreateTorrent.InfoTab = new Class({
    Extends: Widgets.TabPage,
    
    options: {
        url: '/template/render/html/create_torrent_info.html'
    },
    
    initialize: function() {
        this.parent('Info');
    }
});

Deluge.Widgets.CreateTorrent.TrackersTab = new Class({
    Extends: Widgets.TabPage,
    
    options: {
        url: '/template/render/html/create_torrent_trackers.html'
    },
    
    initialize: function() {
        this.parent('Trackers');
    }
});

Deluge.Widgets.CreateTorrent.WebseedsTab = new Class({
    Extends: Widgets.TabPage,
    
    options: {
        url: '/template/render/html/create_torrent_webseeds.html'
    },
    
    initialize: function() {
        this.parent('Webseeds');
    }
});

Deluge.Widgets.CreateTorrent.OptionsTab = new Class({
    Extends: Widgets.TabPage,
    
    options: {
        url: '/template/render/html/create_torrent_options.html'
    },
    
    initialize: function() {
        this.parent('Options');
    }
});