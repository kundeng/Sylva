// JSHint options

/*global window:true, document:true, setTimeout:true, console:true, jQuery:true,
sylva:true, prompt:true, alert:true, FileReader:true, Processing:true, sigma:true,
clearTimeout */


/****************************************************************************
 * Sigma.js visualization
 ****************************************************************************/

;(function(sylva, sigma, $, window, document, undefined) {

  // The grey color.
  var grey = '#EEE';
  // Layout algorithm state.
  var isDrawing = false;
  // setTimeout id.
  var timeout_id = 0;
  // True when the "Go fullscreen" button is clicked.
  var isFullscreenByButton = false;
  // True when the nodes degrees are calculated.
  var degreesCalculated = false;
  // It saves the link in the Sylva logo when Sylva goes in fullscreen mode.
  var linkLogo;
  // It's used when the user select a layout, for save the original forceAtlas2 coordinates.
  var originalCoorSaved = false;
  // It's true when the user is using forceAtlas2 layout.
  var inForceAtlas2 = true;
  // It's used when the user select a diferent edges shape than the original.
  var defaultEdgeSaved = false;

  var Sigma = {

    init: function() {

      var that = this;
      // Node info.
      var $tooltip;
      // Graph size.
      var size = sylva.size;
      // Node sizes variables.
      var minNodeSize = 1;
      var degreeMinNodeSize = 2;
      var maxNodeSize = 8;
      var fullscreenMaxNodeSize = 8;
      var mediumGraphSize = 20;
      var bigGraphSize = 50;
      var defaultMultiplier = 1;
      var degreeMultiplier = 2;
      var sizeMultiplier = defaultMultiplier;

      // Instanciate Sigma.js and customize rendering.
      var sigInst = new sigma();
      sigInst.addRenderer({
        type: 'canvas',
        container: $('#sigma-container')[0]
      });

      if (sylva.size >= mediumGraphSize && sylva.size < bigGraphSize) {
        maxNodeSize = 6;
      } else if (sylva.size >= bigGraphSize) {
        maxNodeSize = 4;
      }

      sigInst.settings({
        drawLabels: false,
        minNodeSize: minNodeSize,
        maxNodeSize: maxNodeSize * sizeMultiplier
      });

      sigInst.graph.read(sylva.graph);

      // Create the legend.
      $('#node-type-legend').empty();
      var list = $('#node-type-legend').append($('<ul>'));
      list.css({
        listStyleType: 'none',
        marginTop: "5px"
      });
      $.each(sylva.nodetypes, function(nodetypeId, nodetype) {
        list.append($('<li>')
          .css({
            minHeight: "20px",
            paddingLeft: "3px"
          })
          .append($('<i>')
            .addClass("icon-eye-open")
            .addClass("show-hide-nodes")
            .attr("data-action", "hide")
            .attr("data-nodetype-id", nodetypeId)
            .css({
              marginRight: "3px",
              width: "1em",
              height: "1em",
              cursor: "pointer",
              verticalAlign: "-2px"
            }))
          .append($('<span>')
            .addClass("change-nodes-color")
            .attr("data-color", nodetype.color)
            .attr("data-nodetype-id", nodetypeId)
            .css({
              backgroundColor: nodetype.color,
              display: "inline-block",
              width: "16px",
              height: "16px",
              verticalAlign: "middle",
              cursor: "pointer"
            }))
          .append($('<span>')
            .css({
              paddingLeft: "0.3em",
              verticalAlign: "middle"
            })
            .text(nodetype.name)
          )
        );
      });

      var node = null;
      var mouseMovedOnNode = false;
      var mouseMovedOnStage = false;
      var isOverNode = false;
      var nodesInGrey = false;
      var isMouseOverCanvas = false;
      var zoomWheel = false;
      var currentNodeX = 0;
      var currentNodeY = 0;

      $('.sigma-mouse').on('mouseover', function() {
        console.log('MOUSEOVERCANVAS');
        isMouseOverCanvas = true;
      });

      $('.sigma-mouse').on('mouseout', function() {
        console.log('MOUSEOUTCANVAS');
        isMouseOverCanvas = false;
      });

      var treatZoomWheel = function(event) {
        if (zoomWheel) {
          event.preventDefault();

          var zoom = sigma.utils.getDelta(event.originalEvent) > 0;

          var _camera = sigInst.cameras[0];
          var pos = _camera.cameraPosition(currentNodeX, currentNodeY, true);

          zooming(zoom, pos);
        }
      };

      $('#main').on('mousewheel', treatZoomWheel);

      var nodeMouseDown = function(event) {
        console.log('DOWN!');
        var dom = $('.sigma-mouse')[0];
        currentNodeX = sigma.utils.getX(event) - dom.offsetWidth / 2;
        currentNodeY = sigma.utils.getY(event) - dom.offsetHeight / 2;

        $('.sigma-mouse').off('mousedown', nodeMouseDown);
        $('#main').on('mousemove', nodeMouseMove);
        $('#main').on('mouseup', nodeMouseUp);

        sigInst.unbind('outNode', treatOutNode);

        mouseMovedOnNode = false;
        zoomWheel = true;

        $('#main').css('user-select', 'none');

        // Deactivate drag graph.
        sigInst.settings({mouseEnabled: false, enableHovering: false});
        sigInst.refresh();
      };

      var nodeMouseUp = function(event) {
        console.log('UP!');

        $('.sigma-mouse').on('mousedown', nodeMouseDown);
        $('#main').off('mousemove', nodeMouseMove);
        $('#main').off('mouseup', nodeMouseUp);

        var near = false;

        var offset = $('.sigma-mouse').offset()
        var nodeX = node['renderer1:x'];
        var nodeY = node['renderer1:y'];
        var x = event.pageX - offset.left;
        var y = event.pageY - offset.top;
        x = nodeX - x;
        y = nodeY - y;

        if (x >= -5 && x <= 5 && y >= -5 && y <= 5) {
          near = true;
        }

        if (!near) {
          treatOutNode();
        }
        sigInst.bind('outNode', treatOutNode);

        zoomWheel = false;

        if (mouseMovedOnNode) {
          mouseMovedOnNode = false;
        } else {
          nodesInGrey = true;
          grayfyNonNeighborhoodOnly(node);
        }

        $('#main').css('user-select', 'all');

        // Activate drag graph.
        sigInst.settings({mouseEnabled: true, enableHovering: true});
        sigInst.refresh();
      };

      var nodeMouseMove = function(event) {
        console.log(node.label + ' MOVE!');

        that.stop();

        var dom = $('.sigma-mouse')[0];
        var cos = Math.cos(sigInst.cameras[0].angle);
        var sin = Math.sin(sigInst.cameras[0].angle);

        mouseMovedOnNode = true;
        currentNodeX = sigma.utils.getX(event) - dom.offsetWidth / 2;
        currentNodeY = sigma.utils.getY(event) - dom.offsetHeight / 2;

        if (sylva.size > 1) {
          var offset = $('.sigma-mouse').offset()
          var x = event.pageX - offset.left;
          var y = event.pageY - offset.top;

          var nodes = sigInst.graph.nodes();
          var ref = [];
          for (var i = 0; i < 2; i++) {
            var n = nodes[i];
            var aux = {
              x: n.x * cos + n.y * sin,
              y: n.y * cos - n.x * sin,
              renX: n['renderer1:x'],
              renY: n['renderer1:y']
            };
            ref.push(aux);
          }

          // Applying linear interpolation.
          x = ((x - ref[0].renX) / (ref[1].renX - ref[0].renX)) *
            (ref[1].x - ref[0].x) + ref[0].x;
          y = ((y - ref[0].renY) / (ref[1].renY - ref[0].renY)) *
            (ref[1].y - ref[0].y) + ref[0].y;

          // Rotating the coordinates.
          node.x = x * cos - y * sin;
          node.y = y * cos + x * sin;

          if (inForceAtlas2) {
            originalCoorSaved = false;
          }
          sigInst.refresh();
        }
      };

      var stageMouseDown = function(event) {
        console.log('DOWN! - STAGE');

        $('.sigma-mouse').off('mousedown', stageMouseDown);
        $('.sigma-mouse').on('mousemove', stageMouseMove);
        $('.sigma-mouse').on('mouseup', stageMouseUp);

        mouseMovedOnStage = false;

        $('#main').css('user-select', 'none');

        sigInst.unbind('overNode', treatOverNode);
      };

      var stageMouseUp = function(event) {
        console.log('UP! - STAGE');

        $('.sigma-mouse').on('mousedown', stageMouseDown);
        $('.sigma-mouse').off('mousemove', stageMouseMove);
        $('.sigma-mouse').off('mouseup', stageMouseUp);

        sigInst.bind('overNode', treatOverNode);

        $('#main').css('user-select', 'all');

        if (mouseMovedOnStage) {
          mouseMovedOnStage = false;
        } else if (nodesInGrey) {
          nodesInGrey = false;
          ungrayfyAllNodes();
        }
      };

      var stageMouseMove = function(event) {
        console.log('MOVE! - STAGE');

        mouseMovedOnStage = true;
      };

      var treatOverNode = function(event) {
        console.log('ALMOST OVERNODE!');
        if (!isOverNode) {
          console.log('OVERNODE!');

          node = event.data.node;
          sylva.Utils.updateNodeLegend(node.id, node.label, 'element-info');

          // Binding mouse node events.
          $('.sigma-mouse').on('mousedown', nodeMouseDown);

          // Unbinding stage mouse events.
          $('.sigma-mouse').off('mousedown', stageMouseDown);

          isOverNode = true;
        }
      };

      var treatOutNode = function(event) {
        console.log('ALMOST OUTNODE!');
        if (isOverNode) {
          console.log('OUTNODE!');

          // Unbinding mouse node events.
          $('.sigma-mouse').off('mousedown', nodeMouseDown);

          // Binding stage mouse events.
          $('.sigma-mouse').on('mousedown', stageMouseDown);

          isOverNode = false;
        }
      };

      sigInst.bind('overNode', treatOverNode);
      sigInst.bind('outNode', treatOutNode);

      $('.sigma-mouse').on('mousedown', stageMouseDown);

      var graphToIds = function(graph) {
        ids = {
          'nodes': [],
          'edges': []
        };

        for (var i = 0; i < graph['nodes'].length; i++) {
          ids['nodes'].push(graph['nodes'][i].id);
        }

        for (var i = 0; i < graph['edges'].length; i++) {
          ids['edges'].push(graph['edges'][i].id);
        }

        return ids;
      };

      var grayfyNonNeighborhoodOnly = function(center) {
        console.log("GRAYFING!")
        neighborhood = sigInst.graph.neighborhood(center.id);
        neighborhoodIds = graphToIds(neighborhood);

        sigInst.graph.nodes().forEach(function(n) {
          if (neighborhoodIds['nodes'].indexOf(n.id) >= 0) {
            n.color = sylva.nodetypes[n.nodetypeId].color;
            delete n['type'];
          } else {
            n.color = grey;
            n.type = 'grey';
          }
        });

        sigInst.graph.edges().forEach(function(e) {
          if (neighborhoodIds['edges'].indexOf(e.id) >= 0) {
            e.color = sigInst.graph.nodes(e.source).color;
          } else {
            e.color = grey;
          }
        });

        // Re-draw graph.
        sigInst.refresh();
      };

      var ungrayfyAllNodes = function() {
        console.log("UNGRAYFING!")
        sigInst.graph.nodes().forEach(function(n) {
          n.color = sylva.nodetypes[n.nodetypeId].color
          delete n['type'];
        });

        sigInst.graph.edges().forEach(function(e) {
          e.color = sigInst.graph.nodes(e.source).color;
        });

        // Re-draw graph.
        sigInst.refresh();
      };

      // Bind pause button.
      $('#sigma-pause').on('click', function() {
        if (isDrawing === true) {
          that.stop();
        } else {
          that.start();
        }
      });

      $('#sigma-export-image').on('mouseover', function() {
        that.stop();
      });

      // Hide/show nodes by type.
      $('.show-hide-nodes').on('click', function() {
        var nodetypeId = $(this).attr('data-nodetype-id');
        var nodesId = sylva.nodetypes[nodetypeId].nodes
        var action = $(this).attr('data-action');
        var hidden;

        if (action == "hide") {
          $(this).attr('data-action', 'show');
          $(this).removeClass('icon-eye-open');
          $(this).addClass('icon-eye-close');
          hidden = true;
        } else {
          $(this).attr('data-action', 'hide');
          $(this).removeClass('icon-eye-close');
          $(this).addClass('icon-eye-open');
          hidden = false;
        }

        sigInst.graph.nodes(nodesId).forEach(function(n) {
          n.hidden = hidden;
        });

        sigInst.refresh();
      });

      // Change the color of the nodes and the legend.
      var changeNodesColor = function(nodetypeId, color, span) {
        var nodesId = sylva.nodetypes[nodetypeId].nodes
        var currentColor = $(span).css('background-color');
        currentColor = new RGBColor(currentColor).toHex().toUpperCase();
        if (currentColor != color) {
          sigInst.graph.nodes(nodesId).forEach(function(n) {
            n.color = color;
          });
          sigInst.graph.edges().forEach(function(e) {
            e.color = sigInst.graph.nodes(e.source).color;
          });
          $(span).css({
            backgroundColor: color
          });
          sigInst.refresh();
        }
      };

      /* Change the color of the nodes and the legend when the user is
       * selecting it in the widget.
       */
      var changeColorWidget = function(span, hex) {
        var nodetypeId = $(span).attr('data-nodetype-id');
        var newColor = '#' + hex
        changeNodesColor(nodetypeId, newColor, span);
      };

      /* Restore the color of the nodes and the legend when the user click out
       * of the widget.
       */
      var hideColorWidget = function(span, picker) {
        if ($(picker).is(':visible')) {
          var nodetypeId = $(span).attr('data-nodetype-id');
          var oldColor = $(span).attr('data-color');
          $(span).colpickSetColor(oldColor.substr(1));
          changeNodesColor(nodetypeId, oldColor, span);
        }
      };

      /* Change the color of the nodes and the legend and submit to server.
       * Also, restore the color if the request fails.
       */
      var submitColorWidget = function(span, hex) {
        var nodetypeId = $(span).attr('data-nodetype-id');
        var newColor = '#' + hex;
        var oldColor = $(span).attr('data-color');
        changeNodesColor(nodetypeId, newColor, span);
        $(span).attr('data-color', newColor);
        sylva.nodetypes[nodetypeId].color = newColor;
        $(span).colpickHide();
        params = {
          nodetypeId: nodetypeId,
          color: newColor
        };
        var jqxhr = $.post(sylva.edit_nodetype_color_ajax_url, params, 'json');
        jqxhr.error(function() {
          changeNodesColor(nodetypeId, oldColor, span);
          $(span).attr('data-color', oldColor);
          sylva.nodetypes[nodetypeId].color = oldColor;
          alert(gettext("Oops! Something went wrong with the server."));
        });
      };

      // Change nodes color.
      $('.change-nodes-color').each(function(i, span) {
        var currentColor = $(span).attr('data-color');
        $(span).colpick({
          colorScheme: 'light',
          layout: 'hex',
          submitText: 'Ok',
          color: currentColor.substr(1),  // Colpick doesn't need the '#' char.
          onChange: function(hsb, hex, rgb, el, bySetColor) {
            changeColorWidget(span, hex.toUpperCase());
          },
          onHide: function(picker) {
            hideColorWidget(span, picker);
          },
          onSubmit: function(hsb, hex, rgb, el, bySetColor) {
            submitColorWidget(span, hex.toUpperCase());
          }
        });
      });

      // Save as a PNG image.
      $('#sigma-export-image').on('click', function() {
        var $canvas = $('<canvas id="sigma_export_image">');
        var width = $('#sigma-container').children().first().width();
        var height = $('#sigma-container').children().first().height();
        $canvas.attr('width', width);
        $canvas.attr('height', height);
        $('#sigma-container').append($canvas);
        var canvas = $canvas[0];
        var ctx = canvas.getContext('2d');
        ctx.globalCompositeOperation = 'source-over';
        ctx.drawImage($('.sigma-scene')[0], 0, 0);
        var img_data = canvas.toDataURL('image/png');
        $(this).attr('href', img_data.replace('image/png', 'image/octet-stream'));
        $canvas.remove();
      });

      // Go fullscreen.
      $('#sigma-go-fullscreen').on('click', function() {
        var elem = $('body')[0];
        if (elem.requestFullscreen) {
          elem.requestFullscreen();
        } else if (elem.mozRequestFullScreen) {
          elem.mozRequestFullScreen();
        } else if (elem.webkitRequestFullscreen) {
          elem.webkitRequestFullscreen();
        } else if (elem.webkitRequestFullScreen) {
          elem.webkitRequestFullScreen();
        }
      });

      // Exit fullscreen.
      $('#sigma-exit-fullscreen').on('click', function() {
        if (document.exitFullscreen) {
          document.exitFullscreen();
        } else if (document.mozCancelFullScreen) {
          document.mozCancelFullScreen();
        } else if (document.webkitExitFullscreen) {
          document.webkitExitFullscreen();
        } else if (document.webkitCancelFullScreen) {
          document.webkitCancelFullScreen();
        }
      });

      // Handle the fullscreen mode changes.
      var handleFullscreen = function() {
        if(isFullscreenByButton) {
          isFullscreenByButton = false;
          stopFullscreen();
        } else {
          isFullscreenByButton = true;
          goFullscreen();
        }
      };

      /* Update some sizes in fullscreen mode. This function will be called
       * when changes in the size of the screen occurr, e.g., when the user
       * open the developers tools in fullscreen mode.
       */
      var updateSizes = function() {
        var height = $(window).height();
        var width = $(window).width();
        var fullscreenHeader = 51;

        $('header').width(width);
        $('#main').width(width);
        $('div.inside.clearfix').width(width);
        $('#body').width(width);

        var trueHeaderHeight =  $('div.inside.clearfix').height();
        $('#body').height(height - trueHeaderHeight);

        // The new width will be: screenWidth - leftWhiteSpace - canvasInfo- rightWhiteSpace - sigmaWrapperBorder - (safeSpace between canvasInfo and canvas)
        $('#sigma-wrapper').width(width);

        // The new height will be: screenHeight - header - whiteSpace - graphControls - (border + padding from canvasInfo) - whiteSpace
        $('#sigma-wrapper').height(height - fullscreenHeader);

        var top = height - 97;
        var left = width - 52;
        $('#sigma-pause').css({
          top: top + "px",
          left: left + "px"
        });

        sigInst.renderers[0].resize(width, height - fullscreenHeader);
        sigInst.refresh();
      };

      /* Update some sizes and styles in fullscreen mode, but only needed when
       * the fullscreen mode is activated.
       */
      var updateStyles = function() {
        $('#body').css({
          paddingBottom: "0",
          paddingTop: "0"
        });

        $('#sigma-wrapper').css({
          border: "none",
          marginRight: "20px",
          marginTop: "-14px"
        });

        $('.graph-controls').css({
          position: "absolute",
          right: "60px",
          paddingTop: "10px",
          paddingRight: "10px",
          borderRadius: "10px",
          backgroundColor: "rgba(214, 231, 223, 0.5)"
        });

        $('#canvas-info').css({
          position: "absolute",
          zIndex: "100",
          border: "none",
          overflow: "auto",
          padding: "10px",
          height: "auto",
          borderRadius: "10px",
          backgroundColor: "rgba(214, 231, 223, 0.5)"
        });
      };

      // Restore the sizes and styles when exit fullscreen mode.
      var restoreSizesAndStyles = function() {
        $('#sigma-pause').removeAttr('style');
        $('#sigma-wrapper').removeAttr('style');
        $('.graph-controls').removeAttr('style');
        $('#canvas-info').removeAttr('style');
        $('#body').removeAttr('style');
        $('div.inside.clearfix').removeAttr('style');
        $('#main').removeAttr('style');
        $('header').removeAttr('style');

        sigInst.renderers[0].resize();
        sigInst.refresh();
      };

      /* Perform the 'real' fullscreen action. Also perform "sytle" actions
       * that can't be undone with the "restoreSizesAndStyles()" method.
       */
      var goFullscreen = function() {
        $('#sigma-go-fullscreen').hide();
        $('nav.main li').hide();
        $('header.global > h2').hide();
        $('nav.menu').hide();
        $('div.graph-item').hide();
        $('div#footer').hide();

        $('#link-logo').on('click', false);
        $('#link-logo').addClass('disabled');
        linkLogo = $('#link-logo').attr('href');
        $('#link-logo').removeAttr('href');

        $('.title-graph-name').show();
        $('#sigma-exit-fullscreen').parent().show();

        sigInst.settings({
          maxNodeSize: fullscreenMaxNodeSize * sizeMultiplier
        });

        updateSizes();
        updateStyles();

        $(window).on('resize', updateSizes);
      };

      /* Perform the cancelation of the fullscreen mode. Also perform the
       * "remove" of some "sytles" that can't be done with the
       * "restoreSizesAndStyles()" method.
       */
      var stopFullscreen = function() {
        $('#sigma-go-fullscreen').show();
        $('nav.main li').show();
        $('header.global h2').show();
        $('nav.menu').show();
        $('div.graph-item').show();
        $('div#footer').show();

        $('#link-logo').off('click');
        $('#link-logo').removeClass('disabled');
        $('#link-logo').attr('href', linkLogo);

        $('.title-graph-name').hide();
        $('#sigma-exit-fullscreen').parent().hide();

        sigInst.settings({
          maxNodeSize: maxNodeSize * sizeMultiplier
        });

        $(window).off('resize');
        restoreSizesAndStyles();
      };

      // Listeners for handle the "fullscreen" events.
      $(document).on('fullscreenchange', handleFullscreen);
      $(document).on('mozfullscreenchange', handleFullscreen);
      $(document).on('webkitfullscreenchange', handleFullscreen);

      var calculateNodesDegrees = function() {
        var nodes = [];
        for(var key in sylva.nodetypes) {
          nodes = nodes.concat(sylva.nodetypes[key].nodes);
        }

        var totalDegrees = sigInst.graph.degree(nodes);
        var inDegrees = sigInst.graph.degree(nodes, 'in');
        var outDegrees = sigInst.graph.degree(nodes, 'out');

        sigInst.graph.nodes().forEach(function(n) {
          var index = nodes.indexOf(n.id);
          n.defaultSize = 1;
          n.totalDegree = totalDegrees[index];
          n.inDegree = inDegrees[index];
          n.outDegree = outDegrees[index];
        });
      };

      var gridLayout = function() {
        if(!degreesCalculated) {
          calculateNodesDegrees();
        }

        var sorted = sigInst.graph.nodes();
        sorted.sort(function (a, b) {
            return b.totalDegree - a.totalDegree;
        });

        sorted = graphToIds({'nodes': sorted, 'edges': []})['nodes'];

        var side = Math.ceil(Math.sqrt(sylva.size));

        sigInst.graph.nodes().forEach(function(n) {
          if (!originalCoorSaved) {
            n.originalX = n.x;
            n.originalY = n.y;
          }
          var i = sorted.indexOf(n.id);
          n.gridX = 100 * (i % side);
          n.gridY = 100 * Math.floor(i / side);
        });

        originalCoorSaved = true;
      };

      var circularLayout = function() {
        sigInst.graph.nodes().forEach(function(n, i) {
          if (!originalCoorSaved) {
            n.originalX = n.x;
            n.originalY = n.y;
          }
          n.circularX = Math.cos(Math.PI * 2 * i / sylva.size - Math.PI / 2),
          n.circularY = Math.sin(Math.PI * 2 * i / sylva.size - Math.PI / 2)
        });

        originalCoorSaved = true;
      };

      // Control graph layout.
      var graphLayoutSelect = $('#sigma-graph-layout');
      graphLayoutSelect.change(function() {
        var xPos = '';
        var yPos = '';

        var type = $(this).find('option:selected').attr('id');
        switch(type) {
          case 'label':
            break;
          case 'force-atlas-2':
            if (originalCoorSaved) {
              xPos = 'originalX';
              yPos = 'originalY';
              originalCoorSaved = false;
            } else {
              return;
            }
            inForceAtlas2 = true;
            break;
          case 'grid':
            that.stop();
            gridLayout();
            xPos = 'gridX';
            yPos = 'gridY';
            inForceAtlas2 = false;
            break;
          case 'circular':
            that.stop();
            circularLayout();
            xPos = 'circularX';
            yPos = 'circularY';
            inForceAtlas2 = false;
            break;
          default:
            break;
        }
        sigma.plugins.animate(sigInst, {x: xPos, y: yPos}, {duration: 500});
      });

      // Control node size.
      var nodeSizeSelect = $('#sigma-node-size');
      nodeSizeSelect.change(function() {
        if(!degreesCalculated) {
          calculateNodesDegrees();
        }

        var animationSize = '';

        var type = $(this).find('option:selected').attr('id');
        var auxMinNodeSize = sigInst.settings('minNodeSize');
        var auxMaxNodeSize = sigInst.settings('maxNodeSize') / sizeMultiplier;
        switch(type) {
          case 'label':
            break;
          case 'same':
            animationSize = 'defaultSize';
            sizeMultiplier = defaultMultiplier;
            break;
          case 'total-degree':
            animationSize = 'totalDegree';
            auxMinNodeSize = degreeMinNodeSize;
            sizeMultiplier = degreeMultiplier;
            break;
          case 'in-degree':
            animationSize = 'inDegree';
            auxMinNodeSize = degreeMinNodeSize;
            sizeMultiplier = degreeMultiplier;
            break;
          case 'out-degree':
            animationSize = 'outDegree';
            auxMinNodeSize = degreeMinNodeSize;
            sizeMultiplier = degreeMultiplier;
            break;
          default:
            break;
        }
        sigInst.settings({
          minNodeSize: auxMinNodeSize,
          maxNodeSize: auxMaxNodeSize * sizeMultiplier
        });
        sigInst.refresh();
        sigma.plugins.animate(sigInst, {size: animationSize}, {duration: 500});
      });

      // Control edges shape.
      var edgeShapeSelect = $('#sigma-edge-shape');
      edgeShapeSelect.change(function() {

        var type = $(this).find('option:selected').attr('id');
        switch(type) {
          case 'label':
            break;
          case 'straight':
            if (defaultEdgeSaved) {
              sigma.canvas.edges.def = sigma.canvas.edges.defBackup;
            } else {
              return;
            }
            break;
          case 'arrow':
            if (!defaultEdgeSaved) {
              sigma.canvas.edges.defBackup = sigma.canvas.edges.def;
              defaultEdgeSaved = true;
            }
            sigma.canvas.edges.def = sigma.canvas.edges.arrow;
            break;
          case 'curve':
            if (!defaultEdgeSaved) {
              sigma.canvas.edges.defBackup = sigma.canvas.edges.def;
              defaultEdgeSaved = true;
            }
            sigma.canvas.edges.def = sigma.canvas.edges.curve;
            break;
          default:
            break;
        }
        sigInst.refresh();
      });

      var zooming = function(zoomIn, position) {
        var _settings = sigInst.settings;
        var _camera = sigInst.cameras[0];
        var _target = $('#sigma-container');

        var pos,
          count,
          ratio,
          newRatio;

        ratio = zoomIn ?
          1 / _settings('zoomingRatio') :
          _settings('zoomingRatio');

        // Deal with min / max:
        newRatio = Math.max(
          _settings('zoomMin'),
          Math.min(
            _settings('zoomMax'),
            _camera.ratio * ratio
          )
        );
        ratio = newRatio / _camera.ratio;

        // Check that the new ratio is different from the initial one:
        if (newRatio !== _camera.ratio) {
          count = sigma.misc.animation.killAll(_camera);

          sigma.misc.animation.camera(
            _camera,
            {
              x: position.x * (1 - ratio) + _camera.x,
              y: position.y * (1 - ratio) + _camera.y,
              ratio: newRatio
            },
            {
              easing: count ? 'quadraticOut' : 'quadraticInOut',
              duration: _settings('mouseZoomDuration')
            }
          );
        }

      };

      $('#sigma-zoom-in').on('click', function(event) {
        zooming(true, {x: 0, y: 0});
      });

      $('#sigma-zoom-out').on('click', function(event) {
        zooming(false, {x: 0, y: 0});
      });

      sigInst.startForceAtlas2();
      isDrawing = true;

      var timeout;
      if (size <= 20) {
        timeout = 10000;
      } else if (size <= 50) {
        timeout = 15000;
      } else if (size <= 100) {
        timeout = 20000;
      } else {
        timeout = 30000;
      }
      that.addTimeout(timeout);

      sigInst.refresh();
    },

    // Start layout algorithm.
    start: function() {
      var sigInst = sigma.instances()[0];
      if (sigInst) {
        sigInst.startForceAtlas2();
      } else {
        Sigma.init();
      }
      isDrawing = true;
      $('#sigma-pause').html('Pause');
      sigma.canvas.hovers.defBackup = sigma.canvas.hovers.def;
      sigma.canvas.hovers.def = sigma.canvas.hovers.info;
    },

    // Stop layout algorithm.
    stop: function() {
      this.removeTimeout();
      var sigInst = sigma.instances()[0];
      if (sigInst) {
        sigInst.stopForceAtlas2();
        isDrawing = false;
        $('#sigma-pause').html('Play');
      }
    },

    // Stop layout algorithm after `timeout` ms.
    addTimeout: function(timeout) {
      var that = this;
      timeout_id = setTimeout(function() {
        that.stop();
      }, timeout);
    },

    // Clear setTimeout.
    removeTimeout: function() {
      clearTimeout(timeout_id);
    }

  };

  // Reveal module.
  window.sylva.Sigma = Sigma;

})(sylva, sigma, jQuery, window, document);
