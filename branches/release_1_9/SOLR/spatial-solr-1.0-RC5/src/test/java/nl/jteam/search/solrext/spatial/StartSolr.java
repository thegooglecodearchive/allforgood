/*
 * Copyright (c) 2009 JTeam B.V.
 * www.jteam.nl
 * All rights reserved.
 *
 * This software is the confidential and proprietary information of
 * JTeam B.V. ("Confidential Information").
 * You shall not disclose such Confidential Information and shall use
 * it only in accordance with the terms of the license agreement you
 * entered into with JTeam.
 */

package nl.jteam.search.solrext.spatial;

import org.apache.solr.servlet.SolrDispatchFilter;
import org.mortbay.jetty.Connector;
import org.mortbay.jetty.Server;
import org.mortbay.jetty.bio.SocketConnector;
import org.mortbay.jetty.servlet.Context;
import org.mortbay.jetty.servlet.ServletHolder;
import org.mortbay.jetty.webapp.WebAppContext;
import org.mortbay.resource.FileResource;

import javax.servlet.http.HttpServlet;
import javax.servlet.http.HttpServletRequest;
import javax.servlet.http.HttpServletResponse;
import javax.servlet.ServletException;
import java.io.File;
import java.io.IOException;

/**
 * A simple utility that starts Solr with the configuration that points to system property solr.solr.home
 *
 * @author Martijn van Groningen
 * @since Sep 25, 2009
 */
public class StartSolr {

    public static void main(String... args) throws Exception {
        Server server = new Server();

        SocketConnector connector = new SocketConnector();
        connector.setMaxIdleTime(1000 * 60 * 60);
        connector.setSoLingerTime(-1);
        connector.setPort(8080);
        server.setConnectors(new Connector[] { connector });

        WebAppContext context = new WebAppContext();
        context.setServer(server);
        context.setContextPath("/");
        context.addFilter(SolrDispatchFilter.class, "/*", Context.SESSIONS);
        context.addServlet(new ServletHolder(RedirectServlet.class), "/*");
        File file = new File("");
        context.setBaseResource(new FileResource(file.toURI().toURL()));

        server.addHandler(context);

        try {
          System.out.println(">>> STARTING EMBEDDED JETTY SERVER, PRESS ANY KEY TO STOP");
          server.start();
          while (System.in.available() == 0) {
            Thread.sleep(5000);
          }
          server.stop();
          server.join();
        }
        catch (Exception e) {
          e.printStackTrace();
          System.exit(100);
        }
    }

    public final static class RedirectServlet extends HttpServlet {

        protected void doGet(HttpServletRequest req, HttpServletResponse resp) throws ServletException, IOException {
            resp.setHeader("Location", "/select?q=*:*");
            resp.setStatus(HttpServletResponse.SC_MOVED_PERMANENTLY);
        }
    }

}
